"""Postgres + pgvector backend. Compatible with an existing AMA 2.x `dilemmas` table (adds columns it needs).
Requires: pip install "artificialmoralagent[postgres]"."""
from __future__ import annotations

import threading

from ..config import get_settings
from .base import JSON_FIELDS, Store, now_iso


class PostgresStore(Store):
    backend = "postgres"

    def __init__(self, url: str):
        try:
            import psycopg2
            import psycopg2.extras
            import psycopg2.pool
        except ImportError as e:
            raise RuntimeError('Postgres support is not installed: pip install "artificialmoralagent[postgres]"') from e
        self._extras = psycopg2.extras
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(1, 8, url)
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Postgres ({e.__class__.__name__}). AMA will not fall back to "
                               f"SQLite automatically; fix AMA_DATABASE_URL or clear it to use SQLite.") from e
        self.dim = get_settings().embed_dim
        self._lock = threading.Lock()

    def _q(self, sql, args=(), fetch="all"):
        conn = self.pool.getconn()
        try:
            with conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all" and cur.description:
                    return cur.fetchall()
                return cur.rowcount
        finally:
            self.pool.putconn(conn)

    def init(self):
        stmts = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            f"""CREATE TABLE IF NOT EXISTS dilemmas (id VARCHAR(36) PRIMARY KEY, dilemma_text TEXT NOT NULL,
                embedding vector({self.dim}), utilitarian_response JSONB, deontology_response JSONB,
                virtue_ethics_response JSONB, care_ethics_response JSONB, verdict JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'done', model_details VARCHAR(100), prompt_version VARCHAR(50),
                thumbs_up_down INTEGER, created_at TIMESTAMP DEFAULT now())""",
            "ALTER TABLE dilemmas ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'done'",
            "ALTER TABLE dilemmas ADD COLUMN IF NOT EXISTS extra JSONB",
            "ALTER TABLE dilemmas ADD COLUMN IF NOT EXISTS published BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE dilemmas ADD COLUMN IF NOT EXISTS source VARCHAR(40)",
            "ALTER TABLE dilemmas ALTER COLUMN model_details TYPE VARCHAR(120)",
            "CREATE INDEX IF NOT EXISTS dilemmas_status_created ON dilemmas(status, created_at)",
            "CREATE TABLE IF NOT EXISTS ama_users (name TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TIMESTAMP)",
            """CREATE TABLE IF NOT EXISTS ama_api_keys (key_id TEXT PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, label TEXT,
                owner TEXT, created_at TIMESTAMP, revoked BOOLEAN NOT NULL DEFAULT FALSE, last_used TIMESTAMP)""",
            "CREATE TABLE IF NOT EXISTS ama_usage (day DATE, who TEXT, kind TEXT, cost DOUBLE PRECISION, at TIMESTAMP)",
            "CREATE INDEX IF NOT EXISTS ama_usage_day ON ama_usage(day, who, kind)",
        ]
        for s in stmts:
            try:
                self._q(s, fetch=None)
            except Exception as e:
                if "CREATE EXTENSION" in s:
                    raise RuntimeError(f"pgvector is not available in this Postgres: {e}") from e
        try:
            if self.dim <= 2000:
                self._q("CREATE INDEX IF NOT EXISTS dilemmas_embedding_hnsw_idx ON dilemmas USING hnsw "
                        "(embedding vector_cosine_ops)", fetch=None)
        except Exception:
            pass

    @staticmethod
    def _vec(v):
        return "[" + ",".join(f"{x:.7f}" for x in v) + "]"

    def _row(self, r):
        if r is None:
            return None
        d = dict(r)
        d.pop("embedding", None)
        if d.get("created_at") is not None and not isinstance(d["created_at"], str):
            d["created_at"] = d["created_at"].isoformat(timespec="seconds")
        if "published" not in d or d["published"] is None:
            d["published"] = True
        return d

    def add(self, rec):
        J = self._extras.Json
        cols = ["id", "dilemma_text", *JSON_FIELDS, "status", "model_details", "prompt_version", "thumbs_up_down",
                "created_at", "published", "source"]
        vals = [J(rec.get(c)) if c in JSON_FIELDS and rec.get(c) is not None else rec.get(c) for c in cols]
        vals[cols.index("created_at")] = rec.get("created_at") or now_iso()
        vals[cols.index("published")] = bool(rec.get("published", True))
        emb_sql, emb_val = "", []
        if rec.get("embedding"):
            cols.append("embedding")
            emb_sql = ",%s::vector"
            emb_val = [self._vec(rec["embedding"])]
        ph = ",".join(["%s"] * (len(cols) - (1 if emb_val else 0))) + emb_sql
        self._q(f"INSERT INTO dilemmas ({','.join(cols)}) VALUES ({ph})", [*vals, *emb_val], fetch=None)
        return self.get(rec["id"])

    def update(self, dilemma_id, fields):
        J = self._extras.Json
        sets, vals = [], []
        for k, v in fields.items():
            if k == "embedding":
                if v:
                    sets.append("embedding=%s::vector")
                    vals.append(self._vec(v))
                continue
            sets.append(f"{k}=%s")
            vals.append(J(v) if k in JSON_FIELDS and v is not None else v)
        if sets:
            self._q(f"UPDATE dilemmas SET {','.join(sets)} WHERE id=%s", [*vals, dilemma_id], fetch=None)
        return self.get(dilemma_id)

    def get(self, dilemma_id):
        return self._row(self._q("SELECT * FROM dilemmas WHERE id=%s", (dilemma_id,), "one"))

    def list(self, status="done", published_only=False, limit=25, offset=0):
        where, args = [], []
        if status:
            where.append("status=%s")
            args.append(status)
            if status == "done":
                where.append("verdict IS NOT NULL")
        if published_only:
            where.append("published")
        sql = "SELECT * FROM dilemmas" + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY (status='pending') DESC, created_at DESC LIMIT %s OFFSET %s"
        return [self._row(r) for r in self._q(sql, [*args, int(limit), int(offset)])]

    def find_exact(self, text, model):
        return self._row(self._q("""SELECT * FROM dilemmas WHERE lower(trim(dilemma_text))=lower(trim(%s))
            AND model_details=%s AND status='done' AND verdict IS NOT NULL ORDER BY created_at DESC LIMIT 1""",
                                 (text, model), "one"))

    def similar(self, vec, k=6, model=None, published_only=False):
        where, args = ["status='done'", "verdict IS NOT NULL", "embedding IS NOT NULL"], []
        if model:
            where.append("model_details=%s")
            args.append(model)
        if published_only:
            where.append("published")
        rows = self._q(f"SELECT *, embedding <=> %s::vector AS distance FROM dilemmas WHERE {' AND '.join(where)} "
                       f"ORDER BY distance LIMIT %s", [self._vec(vec), *args, int(k)])
        out = []
        for r in rows:
            dist = float(r.pop("distance"))
            out.append((self._row(r), dist))
        return out

    def export_all(self):
        out = []
        for r in self._q("SELECT *, embedding::text AS _emb FROM dilemmas ORDER BY created_at"):
            emb = r.pop("_emb", None)
            d = self._row(r)
            d["embedding"] = [float(x) for x in emb.strip("[]").split(",")] if emb else None
            out.append(d)
        return out

    def count(self):
        r = self._q("""SELECT count(*) n, count(*) FILTER (WHERE status='pending') p,
                       count(*) FILTER (WHERE published AND status='done') pub FROM dilemmas""", fetch="one")
        return {"total": r["n"], "pending": r["p"], "published": r["pub"]}

    def put_user(self, name, pw_hash, role="admin"):
        self._q("""INSERT INTO ama_users(name, pw_hash, role, created_at) VALUES (%s,%s,%s,now())
                   ON CONFLICT (name) DO UPDATE SET pw_hash=EXCLUDED.pw_hash, role=EXCLUDED.role""",
                (name, pw_hash, role), fetch=None)

    def get_user(self, name):
        r = self._q("SELECT * FROM ama_users WHERE lower(name)=lower(%s)", (name,), "one")
        return dict(r) if r else None

    def list_users(self):
        return [{"name": r["name"], "role": r["role"], "created_at": str(r["created_at"])}
                for r in self._q("SELECT * FROM ama_users ORDER BY name")]

    def add_key(self, key_id, key_hash, label, owner):
        self._q("INSERT INTO ama_api_keys(key_id, key_hash, label, owner, created_at) VALUES (%s,%s,%s,%s,now())",
                (key_id, key_hash, label, owner), fetch=None)

    def key_by_hash(self, key_hash):
        r = self._q("SELECT * FROM ama_api_keys WHERE key_hash=%s AND NOT revoked", (key_hash,), "one")
        if r:
            self._q("UPDATE ama_api_keys SET last_used=now() WHERE key_id=%s", (r["key_id"],), fetch=None)
        return dict(r) if r else None

    def list_keys(self):
        return [{k: (str(r[k]) if r[k] is not None and k in ("created_at", "last_used") else r[k])
                 for k in ("key_id", "label", "owner", "created_at", "revoked", "last_used")}
                for r in self._q("SELECT * FROM ama_api_keys ORDER BY created_at DESC")]

    def revoke_key(self, key_id):
        return self._q("UPDATE ama_api_keys SET revoked=TRUE WHERE key_id=%s", (key_id,), fetch=None) > 0

    def log_usage(self, day, who, kind, cost):
        self._q("INSERT INTO ama_usage(day, who, kind, cost, at) VALUES (%s,%s,%s,%s,now())", (day, who, kind, cost),
                fetch=None)

    def usage_day(self, day, who=None, kind=None):
        where, args = ["day=%s"], [day]
        if who:
            where.append("who=%s")
            args.append(who)
        if kind:
            where.append("kind=%s")
            args.append(kind)
        r = self._q(f"SELECT count(*) n, coalesce(sum(cost),0) c FROM ama_usage WHERE {' AND '.join(where)}", args, "one")
        return int(r["n"]), float(r["c"])
