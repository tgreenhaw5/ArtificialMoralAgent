"""
MCP server: ArtificialMoralAgent as tools for AI agents and assistants.

    ama mcp                     stdio (Claude Desktop, Claude Code, Cursor, VS Code)
    ama mcp --http --port 8411  Streamable HTTP (remote use)

Client config (stdio):  {"command": "uvx", "args": ["artificialmoralagent", "mcp"]}
                        or {"command": "ama", "args": ["mcp"]} after `pipx install artificialmoralagent`

The tools inform a human decision; they are not an authority. Every result carries the disclaimer, and
crisis situations return support resources instead of an analysis.
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import engine, frameworks, providers, safety
from .store import get_store
from .store.base import public, record_from_analysis

mcp = FastMCP(
    "ArtificialMoralAgent",
    instructions=("Structured ethical analysis to inform a human decision: four frameworks (utilitarian, "
                  "deontological, care, virtue) and a Chief Moral Arbiter that blends them by conviction. Use "
                  "quick_check before consequential actions, evaluate_dilemma for a full analysis, and "
                  "compare_options to rank candidate actions. Present results as perspectives, not orders. "
                  + safety.DISCLAIMER),
)


def _slim(result: dict) -> dict:
    """Keep the verdict and each framework's recommendation; drop bulky internals for the agent's context."""
    if result.get("is_crisis"):
        return result
    out = {"verdict": result.get("verdict"), "general_disclaimer": safety.DISCLAIMER, "usage": result.get("usage"),
           "id": result.get("id")}
    for key, field in (("utilitarianism", "utilitarian"), ("deontology", "deontology"),
                       ("care_ethics", "care_ethics"), ("virtue_ethics", "virtue_ethics")):
        fw = result.get(field) or result.get(f"{field}_response") or {}
        out[key] = {"recommended_action": fw.get("recommended_action"), "conviction": fw.get("conviction_score"),
                    "rationale": fw.get("conviction_rationale")}
    return out


@mcp.tool()
async def evaluate_dilemma(dilemma: str, depth: str = "full") -> str:
    """Analyse a moral dilemma across four ethical frameworks and return the Chief Moral Arbiter's verdict,
    each framework's recommended action and conviction (1-10), and dissenting views.
    depth: "full" (all frameworks + arbiter) or "quick" (one fast balanced view)."""
    text = (dilemma or "").strip()
    if len(text) < 10:
        return json.dumps({"error": "Describe the dilemma in at least 10 characters."})
    if depth == "quick":
        return json.dumps(await engine.quick_check(text))
    result = await engine.evaluate(text)
    if not result.get("is_crisis"):
        try:
            rec = get_store().add(record_from_analysis(text, result, published=False, source="mcp"))
            result["id"] = rec["id"]
        except Exception:
            pass
    return json.dumps(_slim(result))


@mcp.tool()
async def quick_check(action: str, context: str = "") -> str:
    """Fast, cheap first view of whether to proceed with an action: proceed yes/no/with_care, main concerns,
    who is affected, and whether a full analysis is advisable. Use before consequential actions."""
    return json.dumps(await engine.quick_check(action, context))


@mcp.tool()
async def compare_options(situation: str, options: list[str]) -> str:
    """Rank 2-5 candidate actions for a situation across the four frameworks. Returns the arbiter's leading
    option, each framework's preferred option with conviction, and dissenting perspectives."""
    opts = [o.strip() for o in options if o and o.strip()][:5]
    if len(opts) < 2:
        return json.dumps({"error": "Give at least two options."})
    text = (f"{situation.strip()}\n\nThe options being considered are:\n"
            + "\n".join(f"{i + 1}. {o}" for i, o in enumerate(opts))
            + "\n\nEvaluate these specific options and recommend one of them (by its wording).")
    return json.dumps(_slim(await engine.evaluate(text)))


@mcp.tool()
def explain_framework(name: str) -> str:
    """Explain what an ethical framework weighs: utilitarianism, deontology, care_ethics, virtue_ethics or arbiter."""
    if name == "arbiter":
        return ("Chief Moral Arbiter: blends the frameworks' recommended actions by their conviction weights (1-10). "
                "With high agreement it states the shared duty; otherwise it reports the leading action by summed "
                "weight and presents dissenting perspectives.")
    fw = frameworks.get(name)
    if not fw:
        return f"Unknown framework. Choose from: {', '.join(f.key for f in frameworks.active())}, arbiter."
    return f"{fw.title}: {fw.description}"


@mcp.tool()
async def search_precedents(query: str, k: int = 5) -> str:
    """Find similar dilemmas already evaluated in this server's knowledge base, with their verdict titles."""
    st = get_store()
    try:
        hits = st.similar(await providers.embed(query, "query"), k=max(1, min(k, 10)))
    except Exception:
        hits = [(r, None) for r in st.list("done", limit=200) if query.lower() in r["dilemma_text"].lower()][:k]
    out = []
    for r, d in hits:
        p = public(r)
        out.append({"id": p["id"], "dilemma": p["dilemma_text"][:500],
                    "verdict": (p.get("verdict") or {}).get("verdict_title"),
                    "ruling": (p.get("verdict") or {}).get("definitive_ruling"),
                    "distance": None if d is None else round(d, 4)})
    return json.dumps(out)


@mcp.resource("ama://frameworks")
def frameworks_resource() -> str:
    return json.dumps([{"key": f.key, "title": f.title, "description": f.description} for f in frameworks.active()])


@mcp.resource("ama://evaluations/{evaluation_id}")
def evaluation_resource(evaluation_id: str) -> str:
    return json.dumps(safety.with_disclaimer(public(get_store().get(evaluation_id)) or {"error": "not found"}))


@mcp.prompt()
def ethics_review(plan: str) -> str:
    """Ethics review of a plan before acting."""
    return (f"Before acting on this plan, call quick_check; if it suggests a full analysis, call evaluate_dilemma. "
            f"Summarise the perspectives for the human, including dissent, and let them decide.\n\nPlan:\n{plan}")


@mcp.prompt()
def stakeholder_check(decision: str) -> str:
    """Who is affected by a decision, and how?"""
    return (f"Use evaluate_dilemma on this decision and list every stakeholder the frameworks identify, with the "
            f"care-ethics view of the most vulnerable.\n\nDecision:\n{decision}")


def run(http: bool = False, host: str = "127.0.0.1", port: int = 8411):
    if http:
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
