"""
The evaluation pipeline (a 2-stage DAG):

    Stage 0  safety triage (always; local keyword backstop if the model call fails)
    Stage 1  the frameworks in parallel, each with a conviction weight
    Stage 2  the Chief Moral Arbiter (weighted conviction blend) + the embedding for search

`evaluate_stream()` yields each stage as it finishes (used for streaming in the API);
`evaluate()` returns the final result.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from . import frameworks, prompts, providers, safety
from .config import get_settings

log = logging.getLogger("ama.engine")


def _add(total: dict, u: dict):
    for k in ("tokens_in", "tokens_out", "cost_usd"):
        total[k] = round(total.get(k, 0) + (u.get(k) or 0), 6)


async def triage(text: str) -> tuple[dict, dict]:
    s = get_settings()
    local = safety.keyword_triage(text)
    try:
        result, usage = await providers.complete_json(prompts.TRIAGE_PROMPT.format(fenced=prompts.fence(text)),
                                                      s.stage_model("triage"), "triage", retries=1, max_tokens=512)
        result = {"is_crisis": bool(result.get("is_crisis")), "crisis_type": result.get("crisis_type") or "none",
                  "flag_reason": result.get("flag_reason") or "", "method": "model"}
        if local["is_crisis"] and not result["is_crisis"]:
            # the model said no, the keywords say yes: keep the model's call but surface the resources too
            result["resources_shown"] = True
        return result, usage
    except Exception as e:
        log.warning("triage model unavailable, using local check: %s", e)
        return {**local, "method": "local"}, {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}


async def evaluate_stream(text: str, model: str | None = None) -> AsyncIterator[dict]:
    s = get_settings()
    model = model or s.model
    t0 = time.time()
    total = {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
    text = (text or "").strip()

    tri, u = await triage(text)
    _add(total, u)
    yield {"stage": "triage", "result": tri}
    if tri["is_crisis"]:
        yield {"stage": "done", "result": safety.crisis_response(tri, model, prompts.PROMPT_VERSION, total)}
        return

    fws = frameworks.active()
    fw_model = s.framework_model or model
    async def run(fw):
        data, usage = await providers.complete_json(fw.prompt.format(fenced=prompts.fence(text)), fw_model, fw.key)
        return fw, data, usage

    tasks = [asyncio.create_task(run(fw)) for fw in fws]
    emb_task = asyncio.create_task(providers.embed(text, "document"))
    results: dict[str, dict] = {}
    try:
        for fut in asyncio.as_completed(tasks):
            fw, data, usage = await fut
            results[fw.key] = data
            _add(total, usage)
            yield {"stage": "framework", "framework": fw.key, "result": data}
    except Exception:
        for t in tasks:
            t.cancel()
        emb_task.cancel()
        raise

    arb_prompt = prompts.ARBITER_PROMPT.format(
        fenced=prompts.fence(text),
        utilitarian_json=json.dumps(results.get("utilitarianism"), indent=1),
        deontology_json=json.dumps(results.get("deontology"), indent=1),
        care_json=json.dumps(results.get("care_ethics"), indent=1),
        virtue_json=json.dumps(results.get("virtue_ethics"), indent=1))
    extra = [fw for fw in fws if fw not in frameworks.CORE]
    if extra:
        arb_prompt += "\n\nADDITIONAL FRAMEWORKS (blend them the same way):\n" + "\n".join(
            f"{fw.title}:\n{json.dumps(results[fw.key], indent=1)}" for fw in extra)
    verdict, u = await providers.complete_json(arb_prompt, s.arbiter_model or model, "arbiter")
    _add(total, u)
    yield {"stage": "arbiter", "result": verdict}
    try:
        embedding = await emb_task
    except Exception as e:
        log.warning("embedding failed (search will skip this dilemma): %s", e)
        embedding = None
    yield {"stage": "done", "result": safety.with_disclaimer({
        "is_crisis": False,
        "triage": tri,
        "utilitarian": results.get("utilitarianism"),
        "deontology": results.get("deontology"),
        "care_ethics": results.get("care_ethics"),
        "virtue_ethics": results.get("virtue_ethics"),
        "extra_frameworks": {fw.key: results[fw.key] for fw in extra},
        "verdict": verdict,
        "embedding": embedding,
        "model_details": model,
        "prompt_version": prompts.PROMPT_VERSION,
        "usage": {**total, "total_tokens": total["tokens_in"] + total["tokens_out"],
                  "seconds": round(time.time() - t0, 1)},
    })}


async def evaluate(text: str, model: str | None = None) -> dict:
    final = None
    async for ev in evaluate_stream(text, model):
        if ev["stage"] == "done":
            final = ev["result"]
    return final


async def quick_check(action: str, context: str = "") -> dict:
    """Triage + one fast call: a first view of whether to proceed."""
    s = get_settings()
    text = f"Proposed action: {action}\nContext: {context}".strip()
    tri, u0 = await triage(text)
    if tri["is_crisis"]:
        return safety.crisis_response(tri, s.model, prompts.PROMPT_VERSION, u0)
    data, u = await providers.complete_json(prompts.QUICK_PROMPT.format(fenced=prompts.fence(text)),
                                            s.stage_model("triage"), "quick", max_tokens=1024)
    total = {}
    _add(total, u0)
    _add(total, u)
    return safety.with_disclaimer({"is_crisis": False, **data, "usage": total})
