"""
Accounts, sessions, API keys, rate limits and public-demo limits.

- Passwords: salted scrypt (standard library), never stored in plain text.
- Sessions: signed, expiring HttpOnly cookie (`ama_session`).
- API keys: `ama_<id>_<secret>`; only a SHA-256 hash is stored. Sent as `Authorization: Bearer <key>`.
- Rate limit: per client per minute (in memory).
- Public demo: guests get full evaluations on the owner's model key, limited per IP per day, in total per
  day, and by a daily spend cap. Over a limit, the dilemma is queued for review instead.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import date

from .config import get_settings
from .store import get_store

SESSION_COOKIE = "ama_session"
SESSION_DAYS = 7


# ---- passwords -------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        dk = hashlib.scrypt((pw or "").encode(), salt=base64.b64decode(s), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(h))
    except Exception:
        return False


def set_user(name: str, pw: str, role: str = "admin"):
    if len(pw or "") < 10:
        raise ValueError("Use a password of at least 10 characters.")
    get_store().put_user(name.strip(), hash_password(pw), role)


def check_login(name: str, pw: str) -> dict | None:
    u = get_store().get_user(name or "")
    if not u:
        hash_password("timing-equaliser")
        return None
    return u if verify_password(pw, u["pw_hash"]) else None


# ---- sessions ----------------------------------------------------------------
def make_session(user: str) -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    body = f"{user}|{exp}"
    sig = hmac.new(get_settings().ensure_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{body}|{sig}".encode()).decode()


def read_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        user, exp, sig = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 2)
    except Exception:
        return None
    good = hmac.new(get_settings().ensure_secret().encode(), f"{user}|{exp}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or int(exp) < time.time():
        return None
    return user if get_store().get_user(user) else None


# ---- API keys ------------------------------------------------------------------
def create_key(label: str, owner: str) -> str:
    key_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    full = f"ama_{key_id}_{secret}"
    get_store().add_key(key_id, hashlib.sha256(full.encode()).hexdigest(), label, owner)
    return full


def check_key(full: str | None) -> dict | None:
    if not full or not full.startswith("ama_"):
        return None
    return get_store().key_by_hash(hashlib.sha256(full.encode()).hexdigest())


# ---- rate limit ---------------------------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)


def rate_ok(client: str) -> bool:
    limit = get_settings().rate_per_minute
    q = _hits[client]
    now = time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


# ---- public demo --------------------------------------------------------------------
def today() -> str:
    return date.today().isoformat()


def demo_allowance(ip: str) -> tuple[bool, str]:
    """May a guest at this IP run a full evaluation on the owner's key right now?"""
    s = get_settings()
    if not s.public_demo:
        return False, "Public evaluation is not enabled on this server; your dilemma was queued for review."
    st = get_store()
    n_ip, _ = st.usage_day(today(), who=f"ip:{ip}", kind="demo_eval")
    if n_ip >= s.demo_per_ip_per_day:
        return False, (f"You've reached today's limit of {s.demo_per_ip_per_day} free evaluations. Your dilemma was "
                       f"queued for review; you can also run ArtificialMoralAgent yourself with a free Gemini key.")
    n_all, spent = st.usage_day(today(), kind="demo_eval")
    if n_all >= s.demo_per_day or spent >= s.demo_budget_usd_per_day:
        return False, ("The public demo has reached its daily capacity. Your dilemma was queued for review; "
                       "please try again tomorrow, or run ArtificialMoralAgent yourself with a free Gemini key.")
    return True, ""


def record_demo(ip: str, cost: float):
    get_store().log_usage(today(), f"ip:{ip}", "demo_eval", cost)


def kb_public() -> bool:
    """Is the curated knowledge base browsable by guests today?"""
    v = get_settings().kb_public_until.strip().lower()
    if v in ("", "always"):
        return True
    if v in ("off", "never", "false"):
        return False
    try:
        return date.today() <= date.fromisoformat(v)
    except ValueError:
        return True
