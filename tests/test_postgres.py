"""Runs only when AMA_TEST_POSTGRES_URL is set (CI provides a pgvector service container)."""
import os

import pytest
from fastapi.testclient import TestClient

URL = os.environ.get("AMA_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set AMA_TEST_POSTGRES_URL to test the Postgres backend")


def test_postgres_backend_end_to_end(ama_env):
    app = ama_env(AMA_DATABASE_URL=URL, AMA_PUBLIC_DEMO="true")
    from ama import providers, security
    from ama.store import get_store
    st = get_store()
    assert st.backend == "postgres"
    c = TestClient(app)
    security.set_user("pgadmin", "a-long-password")
    tok = c.post("/api/v1/auth/login", json={"user": "pgadmin", "password": "a-long-password"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    text = f"Postgres test dilemma {os.getpid()}: should I report a friend's minor tax fraud?"
    r = c.post("/api/v1/evaluations", headers=h, json={"dilemma": text}).json()
    assert r["verdict"] and r["published"] is True
    assert c.post("/api/v1/evaluations", headers=h, json={"dilemma": text}).json()["cached"]
    hits = st.similar(providers.fake_embedding(text, 768), k=1)
    assert hits[0][0]["id"] == r["id"] and hits[0][1] < 0.01
    rows = st.export_all()
    assert any(x["id"] == r["id"] and len(x["embedding"]) == 768 for x in rows)
    st.log_usage("2026-01-02", "ip:x", "demo_eval", 0.5)
    assert st.usage_day("2026-01-02", kind="demo_eval")[1] >= 0.5
