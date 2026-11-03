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
