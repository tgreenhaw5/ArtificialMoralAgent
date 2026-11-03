
from fastapi.testclient import TestClient

from ama import security

TEXT = "My manager asked me to backdate a contract to meet a deadline. Should I comply?"


def admin(client):
    security.set_user("admin", "a-long-password")
    r = client.post("/api/auth/login", json={"password": "a-long-password"})     # AMA 2.x UI: password only
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health_config_frameworks(ama_env):
    c = TestClient(ama_env())
    assert c.get("/health").json()["database"] == "sqlite"
    cfg = c.get("/api/v1/config").json()
    assert cfg["public_demo"] is False and cfg["disclaimer"] and cfg["default_model"].startswith("gemini/")
    assert {f["key"] for f in c.get("/api/v1/frameworks").json()} >= {"utilitarianism", "arbiter"}
    assert c.get("/").status_code == 200 and c.get("/help/gemini-key").status_code == 200
    assert "aistudio.google.com/app/apikey" in c.get("/help/gemini-key").text


def test_guest_queued_without_demo(ama_env):
    c = TestClient(ama_env())
    r = c.post("/api/dilemmas", json={"dilemma_text": TEXT}).json()
    assert r["queued"] and r["status"] == "pending" and r["general_disclaimer"]
    assert c.get("/api/dilemmas").json() == []           # pending items are never public


def test_public_demo_evaluates_privately_with_limits(ama_env):
    c = TestClient(ama_env(AMA_PUBLIC_DEMO="true", AMA_DEMO_PER_IP_PER_DAY="2"))
    r = c.post("/api/dilemmas", json={"dilemma_text": TEXT, "model": "anthropic/claude-sonnet-5-5"}).json()
    assert r["verdict"] and r["model_details"].startswith("gemini/") and r["published"] is False
    assert c.get(f"/api/v1/evaluations/{r['id']}").status_code == 404     # private until published
    c.post("/api/dilemmas", json={"dilemma_text": TEXT + " Second."})
    third = c.post("/api/dilemmas", json={"dilemma_text": TEXT + " Third."}).json()
    assert third["queued"] and "limit" in third["message"]


def test_admin_flow_cache_search_publish(ama_env):
    c = TestClient(ama_env())
    h = admin(c)
    assert c.get("/api/models", headers=h).json()["default"].startswith("gemini/")
    r = c.post("/api/dilemmas", headers=h, json={"dilemma_text": TEXT, "model": "gemini-3.5-flash-lite"}).json()
    assert r["cached"] is False and r["published"] is True and r["model_details"] == "gemini/gemini-3.5-flash-lite"
    again = c.post("/api/dilemmas", headers=h, json={"dilemma_text": TEXT, "model": "gemini-3.5-flash-lite"}).json()
    assert again["cached"] and again["cache_type"] == "exact_match"
    hits = c.get("/api/search", params={"q": "backdate a contract for my manager"}).json()
    assert hits and hits[0]["id"] == r["id"]
    guest = TestClient(c.app)
    assert [d["id"] for d in guest.get("/api/dilemmas").json()] == [r["id"]]
    c.post(f"/api/v1/dilemmas/{r['id']}/publish", params={"published": "false"}, headers=h)
    assert guest.get("/api/dilemmas").json() == [] and len(c.get("/api/dilemmas").json()) == 1
    assert c.post("/api/dilemmas", headers=h, json={"dilemma_text": TEXT, "model": "evil/model"}).status_code == 400


def test_api_key_v1_and_streaming(ama_env):
    c = TestClient(ama_env())
    h = admin(c)
    key = c.post("/api/v1/keys", headers=h, json={"label": "ci"}).json()["key"]
    kh = {"Authorization": f"Bearer {key}"}
    r = c.post("/api/v1/evaluations", headers=kh, json={"dilemma": TEXT + " v1"}).json()
    assert r["verdict"]["definitive_ruling"] and r["source"] == "api"
    with c.stream("POST", "/api/v1/evaluations?stream=true", headers=kh, json={"dilemma": TEXT + " stream"}) as s:
        body = "".join(s.iter_text())
    events = [l[7:] for l in body.splitlines() if l.startswith("event: ")]
    assert events[0] == "triage" and events.count("framework") == 4 and events[-1] == "done"
    assert c.post("/api/v1/quick-check", headers=kh, json={"action": "Share a friend's secret with their parent"}).json()["proceed"]
    guest = TestClient(c.app)          # no session cookie
    assert guest.post("/api/v1/evaluations", json={"dilemma": TEXT}, params={"stream": "true"}).status_code == 401


def test_crisis_and_input_limits(ama_env):
    c = TestClient(ama_env(AMA_PUBLIC_DEMO="true"))
    r = c.post("/api/dilemmas", json={"dilemma_text": "FAKE_CRISIS everything is too much"}).json()
    assert r["is_crisis"] and r["hotlines"]
    assert c.post("/api/dilemmas", json={"dilemma_text": "short"}).status_code == 400
    assert c.post("/api/dilemmas", json={"dilemma_text": "x" * 5000}).status_code == 413


def test_rate_limit_and_kb_expiry(ama_env):
    c = TestClient(ama_env(AMA_RATE_PER_MINUTE="3", AMA_KB_PUBLIC_UNTIL="2000-01-01"))
    codes = [c.get("/api/search", params={"q": "anything at all"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes
    assert c.get("/api/v1/config").json()["kb_public"] is False


def test_wrong_password_and_headers(ama_env):
    c = TestClient(ama_env())
    security.set_user("admin", "a-long-password")
    assert c.post("/api/v1/auth/login", json={"user": "admin", "password": "nope-nope-nope"}).status_code == 401
    assert c.get("/health").headers["x-content-type-options"] == "nosniff"
    assert c.get("/api/submissions").status_code == 401
