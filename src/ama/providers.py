"""
Model access through LiteLLM: one model string picks the provider.

    gemini/gemini-3.5-flash-lite      Google (GEMINI_API_KEY or GOOGLE_API_KEY)
    anthropic/claude-sonnet-5-5       Anthropic (ANTHROPIC_API_KEY)
    ollama_chat/gemma4:12b-it-qat     local Ollama (OLLAMA_BASE_URL), no key
    openai/<id>                       OpenAI or any OpenAI-compatible server (OPENAI_API_BASE)

AMA_FAKE_LLM=true returns canned, schema-valid answers (tests and CI, no keys, no network).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import re

from .config import get_settings

log = logging.getLogger("ama.providers")

if os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


class ModelError(RuntimeError):
    pass


def extract_json_object(raw: str) -> dict:
    """Parse JSON from model output, tolerating markdown fences and text around the object."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _kwargs(model: str) -> dict:
    s = get_settings()
    kw = {}
    if model.startswith(("ollama/", "ollama_chat/")):
        kw["api_base"] = s.ollama_base_url
    return kw


async def complete_json(prompt: str, model: str, stage: str = "", retries: int = 2,
                        max_tokens: int = 8192) -> tuple[dict, dict]:
    """Returns (parsed JSON, usage {tokens_in, tokens_out, cost_usd})."""
    s = get_settings()
    if s.fake_llm:
        return fake_answer(prompt, stage), {"tokens_in": len(prompt) // 4, "tokens_out": 300, "cost_usd": 0.0}
    import litellm
    litellm.suppress_debug_info = True
    last = None
    messages = [
        {"role": "system", "content": "You are an ethical reasoning engine. Respond only with one valid JSON "
                                      "object matching the requested schema, with no text outside it."},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(retries + 1):
        try:
            kw = dict(model=model, messages=messages, temperature=0.6, max_tokens=max_tokens,
                      timeout=s.request_timeout, **_kwargs(model))
            if not model.startswith(("ollama", "openai/")):
                kw["response_format"] = {"type": "json_object"}
            resp = await litellm.acompletion(**kw)
            text = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            t_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            t_out = int(getattr(usage, "completion_tokens", 0) or 0)
            try:
                cost = float(litellm.completion_cost(completion_response=resp) or 0)
            except Exception:
                cost = 0.0
            try:
                parsed = extract_json_object(text)
            except Exception as e:      # one repair attempt: local models often wrap or truncate JSON
                if attempt < retries:
                    messages = messages + [{"role": "assistant", "content": text[:4000]},
                                           {"role": "user", "content": "That was not valid JSON. Reply again "
                                                                       "with ONLY the JSON object."}]
                    raise ModelError(f"invalid JSON: {e}") from e
                raise
            return parsed, {"tokens_in": t_in, "tokens_out": t_out, "cost_usd": round(cost, 6)}
        except Exception as e:
            last = e
            log.warning("model %s (%s) attempt %d failed: %s", model, stage, attempt + 1, str(e)[:200])
            if attempt < retries:
                await asyncio.sleep(1.0 * (attempt + 1))
    raise ModelError(f"{model} failed for {stage or 'request'}: {str(last)[:300]}")


async def embed(text: str, purpose: str = "document") -> list[float]:
    """Embedding vector of length AMA_EMBED_DIM."""
    s = get_settings()
    if s.fake_llm:
        return fake_embedding(text, s.embed_dim)
    import litellm
    kw = dict(model=s.embed_model, input=[text[:8000]], **_kwargs(s.embed_model))
    if s.embed_model.startswith("gemini/"):
        kw["dimensions"] = s.embed_dim
        kw["task_type"] = "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"
    resp = await litellm.aembedding(**kw)
    vec = list(resp.data[0]["embedding"])
    if len(vec) != s.embed_dim:
        raise ModelError(f"embedding model returned {len(vec)} dimensions, AMA_EMBED_DIM is {s.embed_dim}")
    return vec


# --------------------------------------------------------------------------
# Fake provider (deterministic, schema-valid)
# --------------------------------------------------------------------------
def fake_embedding(text: str, dim: int) -> list[float]:
    words = re.findall(r"[a-z]+", (text or "").lower())
    v = [0.0] * dim
    for w in words:
        h = int(hashlib.sha1(w.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def fake_answer(prompt: str, stage: str) -> dict:
    crisis = "FAKE_CRISIS" in prompt
    if stage == "triage":
        return {"is_crisis": crisis, "crisis_type": "self_harm" if crisis else "none",
                "flag_reason": "test crisis" if crisis else ""}
    if stage == "quick":
        return {"summary": "A balanced first view (test).", "proceed": "with_care", "main_concerns": ["honesty"],
                "who_is_affected": ["you", "others"], "suggest_full_analysis": True}
    base = {"score": 7.5, "recommended_action": "Tell the truth with care", "conviction_score": 7.5,
            "conviction_rationale": "Test rationale."}
    if stage == "utilitarianism":
        return {"framework": "Utilitarianism", **base, "alternative_actions_evaluated": [
            {"action_name": "Tell the truth with care", "d_pleasure_pain": 4, "n_affected": 3, "t_duration_days": 30,
             "p_probability": 0.8, "net_v": 288.0, "analysis": "Test."}],
                "optimal_action": "Tell the truth with care", "consequentialist_summary": "Test summary."}
    if stage == "deontology":
        return {"framework": "Deontological Ethics", **base, "categorical_imperatives": {
            "universal_law": "Test.", "formula_of_humanity": "Test.", "kingdom_of_ends": "Test."},
                "duties_upheld": [{"duty": "Honesty", "type": "Perfect", "justification": "Test."}],
                "duties_violated": [], "permissibility": "Permissible", "deontological_summary": "Test."}
    if stage == "care_ethics":
        return {"framework": "Care Ethics", **base, "vulnerable_stakeholders": [
            {"stakeholder": "Friend", "vulnerability_nature": "Test."}], "relational_impact": "Test.",
                "emotional_and_dependency_needs": "Test.", "care_ethics_summary": "Test."}
    if stage == "virtue_ethics":
        return {"framework": "Virtue Ethics & Sage Council", **base, "sages": [
            {"name": "Inspired by Aristotle", "core_virtue": "Phronesis", "vote": "support", "counsel": "Test."}],
                "council_vote_tally": {"support": 1, "reject": 0, "abstain": 0}, "majority_consensus": "Test.",
                "dissenting_rebuttal": "Test."}
    if stage == "arbiter":
        fw = {k: {"action": "Tell the truth with care", "weight": 7.5, "rationale": "Test."}
              for k in ("utilitarianism", "deontology", "care_ethics", "virtue_ethics")}
        return {"verdict_title": "Tell the truth, with care (test)", "conflict_resolution_principle_applied":
                "Weighted Conviction Blend", "principle_explanation": "Test.", "framework_convictions": fw,
                "alignment_status": "High Alignment", "collective_moral_duty": "Test.",
                "majority_response": {"action": "Tell the truth with care", "combined_weight": 30.0,
                                      "plain_english_summary": "Test."},
                "dissenting_perspectives": [], "definitive_ruling": "Tell the truth with care (test).",
                "actionable_guidance": ["Step 1: Test."]}
    return {}
