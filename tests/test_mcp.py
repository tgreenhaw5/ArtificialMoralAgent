import json

from ama import mcp_server


async def test_mcp_tools(ama_env):
    ama_env()
    r = json.loads(await mcp_server.evaluate_dilemma("Should a doctor tell a patient a frightening prognosis?"))
    assert r["verdict"]["verdict_title"] and r["utilitarianism"]["conviction"] and r["general_disclaimer"]
    q = json.loads(await mcp_server.quick_check("Read my partner's messages", "I suspect cheating"))
    assert q["proceed"]
    c = json.loads(await mcp_server.compare_options("A colleague takes credit for my work.",
                                                    ["Confront them privately", "Tell the manager", "Let it go"]))
    assert c["verdict"]
    assert "felicific" in mcp_server.explain_framework("utilitarianism").lower()
    hits = json.loads(await mcp_server.search_precedents("doctor prognosis"))
    assert hits and hits[0]["verdict"]
    crisis = json.loads(await mcp_server.evaluate_dilemma("FAKE_CRISIS I want it all to stop"))
    assert crisis["is_crisis"] and crisis["hotlines"]


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def test_mcp_over_http_needs_an_api_key(ama_env):
    from fastapi.testclient import TestClient

    from ama import security
    from ama.api import create_app
    ama_env()
    key = security.create_key("mcp-test", "test")
    with TestClient(create_app(mcp_http=True)) as c:        # "with" runs the MCP session manager's startup
        r = c.post("/mcp", json=INIT, headers=MCP_HEADERS)
        assert r.status_code == 401 and "API key" in r.json()["detail"]
        assert c.post("/mcp/", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer ama_bad_key"}).status_code == 401
        for path in ("/mcp", "/mcp/"):
            r = c.post(path, json=INIT, headers={**MCP_HEADERS, "Authorization": f"Bearer {key}"})
            assert r.status_code == 200 and "ArtificialMoralAgent" in r.text, (path, r.status_code, r.text[:200])
        assert c.get("/health").status_code == 200        # the rest of the app is unaffected
