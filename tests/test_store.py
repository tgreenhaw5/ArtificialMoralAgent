
from ama import providers
from ama.store import get_store
from ama.store.base import public, record_from_analysis


def _rec(text, model="gemini/x", published=True):
    a = {"utilitarian": {"a": 1}, "verdict": {"verdict_title": text[:20]}, "model_details": model,
         "prompt_version": "t", "embedding": providers.fake_embedding(text, 768)}
    return record_from_analysis(text, a, published=published)


def test_sqlite_roundtrip_search_and_export(ama_env, tmp_path):
    ama_env()
    st = get_store()
    a = st.add(_rec("lying to protect a friend from harm"))
    st.add(_rec("stealing bread to feed a hungry child"))
    st.add(_rec("private draft", published=False))
    assert st.get(a["id"])["verdict"]["verdict_title"].startswith("lying")
    assert st.find_exact("  LYING to protect a friend from harm ", "gemini/x")["id"] == a["id"]
    hits = st.similar(providers.fake_embedding("is lying to protect a friend ok", 768), k=2)
    assert hits[0][0]["id"] == a["id"] and hits[0][1] < hits[1][1]
    assert len(st.list("done", published_only=True)) == 2 and st.count()["total"] == 3
    rows = st.export_all()
    assert len(rows) == 3 and len(rows[0]["embedding"]) == 768
    assert public(st.get(a["id"]))["published"] is True


def test_usage_and_keys(ama_env):
    ama_env()
    st = get_store()
    st.log_usage("2026-01-01", "ip:1", "demo_eval", 0.01)
    st.log_usage("2026-01-01", "ip:2", "demo_eval", 0.02)
    assert st.usage_day("2026-01-01") == (2, 0.03)
    assert st.usage_day("2026-01-01", who="ip:1")[0] == 1
    from ama import security
    k = security.create_key("ci", "tester")
    assert security.check_key(k)["owner"] == "tester" and security.check_key(k + "x") is None
    kid = k.split("_")[1]
    assert st.revoke_key(kid) and security.check_key(k) is None


def test_cli_export_import(ama_env, tmp_path):
    ama_env()
    from ama.cli import main
    st = get_store()
    st.add(_rec("a curated classic dilemma about promises"))
    out = tmp_path / "x.jsonl"
    main(["db", "export", "-o", str(out), "--published-only"])
    assert len(out.read_text().splitlines()) == 1
    ama_env(AMA_HOME=str(tmp_path / "other"))
    import ama.config as cfg
    cfg.get_settings().home = tmp_path / "other"
    get_store(reload=True)
    main(["db", "import", str(out), "--publish"])
    main(["db", "import", str(out)])
    assert get_store().count()["total"] == 1
