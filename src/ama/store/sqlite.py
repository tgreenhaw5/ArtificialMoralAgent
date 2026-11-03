"""SQLite backend. Vectors are float32 blobs; sqlite-vec's vec_distance_cosine does the search in C when the
extension can be loaded, otherwise a pure-Python cosine over the stored vectors (fine for thousands)."""
from __future__ import annotations

import json
import math
import sqlite3
import struct
import threading
from pathlib import Path

from .base import JSON_FIELDS, Store, now_iso

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS dilemmas (
        id TEXT PRIMARY KEY, dilemma_text TEXT NOT NULL,
        utilitarian_response TEXT, deontology_response TEXT, virtue_ethics_response TEXT,
        care_ethics_response TEXT, verdict TEXT, extra TEXT,
        status TEXT NOT NULL DEFAULT 'done', model_details TEXT, prompt_version TEXT,
        thumbs_up_down INTEGER, created_at TEXT, published INTEGER NOT NULL DEFAULT 1, source TEXT)""",
    "CREATE INDEX IF NOT EXISTS dilemmas_status_created ON dilemmas(status, created_at)",
    "CREATE TABLE IF NOT EXISTS dilemma_vectors (id TEXT PRIMARY KEY, dim INTEGER, vec BLOB)",
    "CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT)",
    """CREATE TABLE IF NOT EXISTS api_keys (key_id TEXT PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, label TEXT,
        owner TEXT, created_at TEXT, revoked INTEGER NOT NULL DEFAULT 0, last_used TEXT)""",
    "CREATE TABLE IF NOT EXISTS usage_log (day TEXT, who TEXT, kind TEXT, cost REAL, at TEXT)",
    "CREATE INDEX IF NOT EXISTS usage_day ON usage_log(day, who, kind)",
    "CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)",
]


def _pack(v):
    return struct.pack(f"{len(v)}f", *v)


def _unpack(b):
    return list(struct.unpack(f"{len(b) // 4}f", b))


def _cos_dist(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return 1.0 - dot / (na * nb)


class SQLiteStore(Store):
    backend = "sqlite"

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.vec_ext = False
        try:
            import sqlite_vec
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
            self.vec_ext = True
        except Exception:
            self.vec_ext = False

    def init(self):
        with self._lock:
            for sql in SCHEMA:
                self.conn.execute(sql)
            self.conn.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('schema_version', '1')")

    def _x(self, sql, args=()):
        with self._lock:
            return self.conn.execute(sql, args)

    @staticmethod
    def _row(r) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        for k in JSON_FIELDS:
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    pass
        return d

    # ---- dilemmas ---------------------------------------------------------
    def add(self, rec: dict) -> dict:
        cols = ["id", "dilemma_text", *JSON_FIELDS, "status", "model_details", "prompt_version", "thumbs_up_down",
                "created_at", "published", "source"]
        vals = [json.dumps(rec.get(c)) if c in JSON_FIELDS and rec.get(c) is not None else rec.get(c) for c in cols]
        vals[cols.index("published")] = 1 if rec.get("published", True) else 0
        vals[cols.index("created_at")] = rec.get("created_at") or now_iso()
        self._x(f"INSERT INTO dilemmas ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        if rec.get("embedding"):
            self._x("INSERT OR REPLACE INTO dilemma_vectors(id, dim, vec) VALUES (?,?,?)",
                    (rec["id"], len(rec["embedding"]), _pack(rec["embedding"])))
        return self.get(rec["id"])

    def update(self, dilemma_id, fields):
        fields = dict(fields)
        emb = fields.pop("embedding", None)
        if fields:
            sets, vals = [], []
            for k, v in fields.items():
                sets.append(f"{k}=?")
                vals.append(json.dumps(v) if k in JSON_FIELDS and v is not None else
                            (1 if v is True else 0 if v is False else v))
            self._x(f"UPDATE dilemmas SET {','.join(sets)} WHERE id=?", [*vals, dilemma_id])
        if emb:
            self._x("INSERT OR REPLACE INTO dilemma_vectors(id, dim, vec) VALUES (?,?,?)",
                    (dilemma_id, len(emb), _pack(emb)))
        return self.get(dilemma_id)

    def get(self, dilemma_id):
        return self._row(self._x("SELECT * FROM dilemmas WHERE id=?", (dilemma_id,)).fetchone())

    def list(self, status="done", published_only=False, limit=25, offset=0):
        where, args = [], []
        if status:
            where.append("status=?")
            args.append(status)
            if status == "done":
                where.append("verdict IS NOT NULL")
        if published_only:
            where.append("published=1")
        sql = "SELECT * FROM dilemmas" + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC LIMIT ? OFFSET ?"
        return [self._row(r) for r in self._x(sql, [*args, int(limit), int(offset)]).fetchall()]

    def find_exact(self, text, model):
        r = self._x("""SELECT * FROM dilemmas WHERE lower(trim(dilemma_text))=lower(trim(?)) AND model_details=?
                       AND status='done' AND verdict IS NOT NULL ORDER BY created_at DESC LIMIT 1""",
                    (text, model)).fetchone()
        return self._row(r)

    def similar(self, vec, k=6, model=None, published_only=False):
        where = ["d.status='done'", "d.verdict IS NOT NULL", "v.dim=?"]
        args = [len(vec)]
        if model:
            where.append("d.model_details=?")
            args.append(model)
        if published_only:
            where.append("d.published=1")
        if self.vec_ext:
            sql = (f"SELECT d.*, vec_distance_cosine(v.vec, ?) AS distance FROM dilemmas d JOIN dilemma_vectors v "
                   f"ON v.id=d.id WHERE {' AND '.join(where)} ORDER BY distance LIMIT ?")
            rows = self._x(sql, [_pack(vec), *args, int(k)]).fetchall()
            return [(self._row({kk: r[kk] for kk in r.keys() if kk != "distance"}), float(r["distance"])) for r in rows]
        rows = self._x(f"SELECT d.*, v.vec AS _vec FROM dilemmas d JOIN dilemma_vectors v ON v.id=d.id "
                       f"WHERE {' AND '.join(where)}", args).fetchall()
        scored = []
        for r in rows:
            d = {kk: r[kk] for kk in r.keys() if kk != "_vec"}
            scored.append((self._row(d), _cos_dist(vec, _unpack(r["_vec"]))))
        scored.sort(key=lambda x: x[1])
        return scored[:k]

    def export_all(self):
        out = []
        for r in self._x("SELECT d.*, v.vec AS _vec FROM dilemmas d LEFT JOIN dilemma_vectors v ON v.id=d.id "
                         "ORDER BY d.created_at").fetchall():
            d = self._row({k: r[k] for k in r.keys() if k != "_vec"})
            d["embedding"] = _unpack(r["_vec"]) if r["_vec"] else None
            out.append(d)
        return out

    def delete(self, dilemma_id):
        with self._lock:
            self.conn.execute("DELETE FROM dilemma_vectors WHERE id=?", (dilemma_id,))
            return self.conn.execute("DELETE FROM dilemmas WHERE id=?", (dilemma_id,)).rowcount > 0

    def count(self):
        r = self._x("""SELECT count(*) n, sum(status='pending') p, sum(published=1 AND status='done') pub
                       FROM dilemmas""").fetchone()
        return {"total": r["n"] or 0, "pending": r["p"] or 0, "published": r["pub"] or 0}

    # ---- accounts & keys ----------------------------------------------------
    def put_user(self, name, pw_hash, role="admin"):
        self._x("INSERT OR REPLACE INTO users(name, pw_hash, role, created_at) VALUES (?,?,?,?)",
                (name, pw_hash, role, now_iso()))

    def get_user(self, name):
        r = self._x("SELECT * FROM users WHERE lower(name)=lower(?)", (name,)).fetchone()
        return dict(r) if r else None

    def list_users(self):
        return [{"name": r["name"], "role": r["role"], "created_at": r["created_at"]}
                for r in self._x("SELECT * FROM users ORDER BY name").fetchall()]

    def add_key(self, key_id, key_hash, label, owner):
        self._x("INSERT INTO api_keys(key_id, key_hash, label, owner, created_at) VALUES (?,?,?,?,?)",
                (key_id, key_hash, label, owner, now_iso()))

    def key_by_hash(self, key_hash):
        r = self._x("SELECT * FROM api_keys WHERE key_hash=? AND revoked=0", (key_hash,)).fetchone()
        if r:
            self._x("UPDATE api_keys SET last_used=? WHERE key_id=?", (now_iso(), r["key_id"]))
        return dict(r) if r else None

    def list_keys(self):
        return [{k: r[k] for k in ("key_id", "label", "owner", "created_at", "revoked", "last_used")}
                for r in self._x("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()]

    def revoke_key(self, key_id):
        return self._x("UPDATE api_keys SET revoked=1 WHERE key_id=?", (key_id,)).rowcount > 0

    # ---- usage ------------------------------------------------------------------
    def log_usage(self, day, who, kind, cost):
        self._x("INSERT INTO usage_log(day, who, kind, cost, at) VALUES (?,?,?,?,?)", (day, who, kind, cost, now_iso()))

    def usage_day(self, day, who=None, kind=None):
        where, args = ["day=?"], [day]
        if who:
            where.append("who=?")
            args.append(who)
        if kind:
            where.append("kind=?")
            args.append(kind)
        r = self._x(f"SELECT count(*) n, coalesce(sum(cost),0) c FROM usage_log WHERE {' AND '.join(where)}", args).fetchone()
        return int(r["n"]), float(r["c"])
