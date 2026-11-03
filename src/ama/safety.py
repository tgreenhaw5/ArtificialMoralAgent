"""
Safety: crisis triage support, resources and disclaimers.

Policy (always on, not configurable):
- Every dilemma goes through safety triage before any ethical analysis.
- If the triage model call fails, a local keyword check is used as a backstop. A dilemma that trips it
  gets the crisis response, never a framework analysis.
- Every response, including cached ones and API/MCP results, carries the disclaimer.
"""
from __future__ import annotations

import re

DISCLAIMER = (
    "ArtificialMoralAgent offers structured ethical analysis to inform a human decision. It is not legal, "
    "medical, psychological or other professional advice, and its frameworks and language models have known "
    "limitations and biases. You remain responsible for your decisions."
)

CRISIS_NOTICE = (
    "EMERGENCY NOTICE: If you or someone you know is in acute danger or experiencing a mental health crisis, "
    "please contact emergency services immediately."
)

HOTLINES = [
    {"name": "Emergency services", "contact": "Call 911 (USA/Canada) or your local emergency number"},
    {"name": "988 Suicide & Crisis Lifeline", "contact": "Call or Text 988 (USA/Canada)"},
    {"name": "The Trevor Project", "contact": "Call 1-866-488-7386 or Text START to 678-678"},
    {"name": "National Domestic Violence Hotline", "contact": "Call 1-800-799-SAFE (7233)"},
    {"name": "International Resources", "contact": "https://findahelpline.com"},
]

# Backstop only (used when the triage model is unavailable). Deliberately broad: a false positive shows
# support resources; a false negative would analyse a crisis as a puzzle.
_PATTERNS = {
    "self_harm": r"\b(kill(ing)? myself|end(ing)? my life|suicid\w*|self[- ]harm\w*|cut(ting)? myself|"
                 r"don'?t want to (live|be alive)|take my own life|overdose)\b",
    "imminent_violence": r"\b(going to|gonna|plan(ning)? to|want to) (kill|shoot|stab|hurt|attack|murder)\b|"
                         r"\b(kill|shoot|stab) (him|her|them|my \w+)\b",
    "abuse": r"\b(he|she|they) (hits|beats|chokes|is hurting) me\b|\bbeing (abused|beaten)\b|\bafraid for my life\b",
}


def keyword_triage(text: str) -> dict:
    low = (text or "").lower()
    for kind, pat in _PATTERNS.items():
        if re.search(pat, low):
            return {"is_crisis": True, "crisis_type": kind,
                    "flag_reason": "Possible crisis language detected (local safety check)."}
    return {"is_crisis": False, "crisis_type": "none", "flag_reason": ""}


def crisis_response(triage: dict, model: str, prompt_version: str, usage: dict) -> dict:
    return {
        "is_crisis": True,
        "crisis_type": triage.get("crisis_type") or "unspecified",
        "flag_reason": triage.get("flag_reason") or "",
        "disclaimer": CRISIS_NOTICE,
        "general_disclaimer": DISCLAIMER,
        "hotlines": HOTLINES,
        "model_details": model,
        "prompt_version": prompt_version,
        "usage": usage,
    }


def with_disclaimer(payload: dict) -> dict:
    payload = dict(payload)
    payload.setdefault("general_disclaimer", DISCLAIMER)
    return payload
