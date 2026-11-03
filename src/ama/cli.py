"""
ama — the ArtificialMoralAgent command.

    ama init                      set up: model preset, API key (with help), admin account, public demo
    ama serve [--host --port]     web app + REST API (+ MCP over HTTP at /mcp with --mcp)
    ama doctor                    check Python, database, model access, embeddings
    ama mcp [--http]              MCP server for AI assistants
    ama evaluate "text"           one evaluation in the terminal (JSON)
    ama db export -o file.jsonl [--published-only]    ama db import file.jsonl [--publish]
    ama user add NAME             create or reset an admin account
    ama keys create LABEL | list | revoke KEY_ID
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

GEMINI_HELP = """
How to get a free Google Gemini API key (about 2 minutes, no credit card):
  1. Open https://aistudio.google.com/apikey and sign in with a Google account.
  2. Accept the terms the first time (the marketing checkbox is optional).
  3. Click "Create API key" (choose "in a new project" if asked) and copy the key. It is shown once.
  4. Paste it below. It is stored only on this computer, in {env}.
Free-tier note: Google may use data sent on the free tier to improve its products, so don't paste
confidential details into dilemmas while using a free key. Free-tier use is rate-limited, not billed.
"""


def _env_set(updates: dict):
    from .config import AMA_HOME, ENV_FILE
    AMA_HOME.mkdir(parents=True, exist_ok=True)
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    done = set()
    out = []
    for line in lines:
        k = line.split("=", 1)[0].strip()
        if k in updates:
            out.append(f"{k}={updates[k]}")
            done.add(k)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in done]
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass
    for k, v in updates.items():
        os.environ[k] = str(v)


def cmd_init(a):
    from .config import ENV_FILE, PRESETS, get_settings
    print("ArtificialMoralAgent setup\n")
    preset = a.preset or (input("Model preset [cloud-cheap / cloud-quality / local] (cloud-cheap): ").strip() or "cloud-cheap")
    if preset not in PRESETS:
        sys.exit(f"Unknown preset {preset}")
    up = dict(PRESETS[preset])
    if preset == "local":
        up["AMA_EMBED_DIM"] = "768"
        print("Local preset: install Ollama, then `ollama pull gemma4:12b-it-qat` and `ollama pull nomic-embed-text`.")
    else:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            print(GEMINI_HELP.format(env=ENV_FILE))
            key = getpass.getpass("Gemini API key (input hidden; blank = later): ").strip()
            if key:
                up["GEMINI_API_KEY"] = key
        if "anthropic" in json.dumps(up) and not os.environ.get("ANTHROPIC_API_KEY"):
            k2 = getpass.getpass("Anthropic API key (for the Claude arbiter; blank = later): ").strip()
            if k2:
                up["ANTHROPIC_API_KEY"] = k2
    db = a.database or input("Database URL (blank = SQLite in ~/.ama, recommended for one computer): ").strip()
    if db:
        up["AMA_DATABASE_URL"] = db
    demo = (input("Allow the public to run evaluations on your key (public demo)? [y/N]: ").strip().lower() == "y")
    up["AMA_PUBLIC_DEMO"] = "true" if demo else "false"
    _env_set(up)
    get_settings(reload=True)
    from .store import get_store
    get_store(reload=True)
    from . import security
    if not get_store().list_users():
        name = input("Admin user name (admin): ").strip() or "admin"
        while True:
            p1 = getpass.getpass("Admin password (10+ characters): ")
            if p1 != getpass.getpass("Repeat: "):
                print("Passwords differ.")
                continue
            try:
                security.set_user(name, p1)
                break
            except ValueError as e:
                print(e)
    print(f"\nSaved settings to {ENV_FILE}. Next: `ama doctor`, then `ama serve`.")


def cmd_serve(a):
    import uvicorn

    from .config import get_settings
    s = get_settings()
    from .api import create_app
    app = create_app()
    if a.mcp:
        from .mcp_server import mcp
        app.mount("/mcp", mcp.streamable_http_app())
    host, port = a.host or s.host, a.port or s.port
    print(f"ArtificialMoralAgent on http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port} "
          f"(API docs at /docs){' · MCP at /mcp' if a.mcp else ''}")
    uvicorn.run(app, host=host, port=port, proxy_headers=True, log_level="warning")


def cmd_doctor(a):
    from .config import ENV_FILE, get_settings, has_cloud_key
    s = get_settings()
    ok = True

    def line(name, good, detail=""):
        nonlocal ok
        ok = ok and good
        print(f"[{'PASS' if good else 'FAIL'}] {name:32} {detail}")

    line("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0])
    line("settings file", True, str(ENV_FILE) + ("" if ENV_FILE.exists() else " (not created yet: run ama init)"))
    try:
        from .store import get_store
        st = get_store()
        line("database", True, f"{st.backend} {st.count()}")
        if st.backend == "sqlite":
            line("vector search (sqlite-vec)", True, "native" if st.vec_ext else "pure-Python fallback (slower)")
        line("admin account", bool(st.list_users()), "" if st.list_users() else "run: ama user add admin")
    except Exception as e:
        line("database", False, str(e)[:200])
    for stage in ("triage", "framework", "arbiter"):
        m = s.stage_model(stage)
        line(f"{stage} model key", has_cloud_key(m), m + ("" if has_cloud_key(m) else
                                                         "  (no key: see `ama init` or /help/gemini-key)"))
    if not a.offline:
        from . import providers
        try:
            asyncio.run(providers.complete_json('Return {"ok": true} as JSON.', s.model, "ping", retries=0, max_tokens=50))
            line("model reachable", True, s.model)
        except Exception as e:
            line("model reachable", False, str(e)[:200])
        try:
            v = asyncio.run(providers.embed("test", "query"))
            line("embeddings", len(v) == s.embed_dim, f"{s.embed_model} → {len(v)} dims")
        except Exception as e:
            line("embeddings", False, str(e)[:200])
    print("\nAll good." if ok else "\nFix the FAIL lines above.")
    return 0 if ok else 1


def cmd_mcp(a):
    from .mcp_server import run
    run(http=a.http, host=a.host, port=a.port)


def cmd_evaluate(a):
    from . import engine
    res = asyncio.run(engine.evaluate(a.text, a.model))
    res.pop("embedding", None)
    print(json.dumps(res, indent=2))


def cmd_db(a):
    from .store import get_store
    st = get_store()
    if a.action == "export":
        rows = st.export_all()
        if a.published_only:
            rows = [r for r in rows if r.get("published", True) and r.get("status") == "done" and r.get("verdict")]
        with open(a.output, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, default=str) + "\n" for r in rows)
        print(f"Exported {len(rows)} dilemmas to {a.output}")
    elif a.action == "import":
        n = skipped = 0
        for line in Path(a.file).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if st.get(r["id"]):
                skipped += 1
                continue
            if a.publish:
                r["published"] = True
            r.setdefault("source", "imported")
            st.add(r)
            n += 1
        print(f"Imported {n} dilemmas ({skipped} already present).")


def cmd_user(a):
    from . import security
    p1 = getpass.getpass(f"Password for {a.name} (10+ characters): ")
    if p1 != getpass.getpass("Repeat: "):
        sys.exit("Passwords differ.")
    security.set_user(a.name, p1)
    print(f"Admin account {a.name} saved.")


def cmd_keys(a):
    from . import security
    from .store import get_store
    if a.action == "create":
        print(security.create_key(a.arg or "integration", "cli"))
        print("Store this key securely; it is not shown again.")
    elif a.action == "list":
        for k in get_store().list_keys():
            print(f"{k['key_id']}  {k['label'] or '':20} {'revoked' if k['revoked'] else 'active':8} last used {k['last_used'] or '-'}")
    elif a.action == "revoke":
        print("revoked" if get_store().revoke_key(a.arg or "") else "no such key")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ama", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("init")
    p.add_argument("--preset")
    p.add_argument("--database")
    p = sub.add_parser("serve")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--mcp", action="store_true", help="also serve MCP (Streamable HTTP) at /mcp")
    p = sub.add_parser("doctor")
    p.add_argument("--offline", action="store_true", help="skip live model calls")
    p = sub.add_parser("mcp")
    p.add_argument("--http", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8411)
    p = sub.add_parser("evaluate")
    p.add_argument("text")
    p.add_argument("--model")
    p = sub.add_parser("db")
    p.add_argument("action", choices=["export", "import"])
    p.add_argument("file", nargs="?")
    p.add_argument("-o", "--output", default="ama-export.jsonl")
    p.add_argument("--published-only", action="store_true")
    p.add_argument("--publish", action="store_true", help="mark imported dilemmas as public")
    p = sub.add_parser("user")
    p.add_argument("action", choices=["add"])
    p.add_argument("name")
    p = sub.add_parser("keys")
    p.add_argument("action", choices=["create", "list", "revoke"])
    p.add_argument("arg", nargs="?")
    sub.add_parser("version")
    a = ap.parse_args(argv)
    if a.cmd == "version":
        from . import __version__
        print(__version__)
        return 0
    fn = {"init": cmd_init, "serve": cmd_serve, "doctor": cmd_doctor, "mcp": cmd_mcp, "evaluate": cmd_evaluate,
          "db": cmd_db, "user": cmd_user, "keys": cmd_keys}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
