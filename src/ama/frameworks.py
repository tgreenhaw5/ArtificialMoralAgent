"""
Ethical frameworks as plug-ins.

Each framework is a prompt that returns JSON with at least: recommended_action, conviction_score,
conviction_rationale. The Chief Moral Arbiter blends their convictions.

Add a framework from your own package with an entry point in pyproject.toml:

    [project.entry-points."ama.frameworks"]
    contractualism = "my_pkg.frameworks:CONTRACTUALISM"

where CONTRACTUALISM = Framework(key="contractualism", title="Contractualism", prompt="...{fenced}...",
description="..."). The four core frameworks always run; plug-ins run when AMA_EXTRA_FRAMEWORKS lists them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import prompts


@dataclass(frozen=True)
class Framework:
    key: str            # result field + stage name
    title: str
    prompt: str         # must contain {fenced}
    description: str
    db_column: str = ""  # legacy column for the 4 core frameworks


CORE = [
    Framework("utilitarianism", "Utilitarianism", prompts.UTILITARIAN_PROMPT,
              "Weighs outcomes: degree, number affected, duration and probability of benefit and harm "
              "(Bentham and Mill's felicific calculus).", "utilitarian_response"),
    Framework("deontology", "Deontological Ethics", prompts.DEONTOLOGY_PROMPT,
              "Weighs duties and rights: Kant's categorical imperative, perfect and imperfect duties, "
              "treating people as ends, never merely as means.", "deontology_response"),
    Framework("care_ethics", "Care Ethics", prompts.CARE_ETHICS_PROMPT,
              "Weighs relationships and vulnerability: trust, dependency and emotional harm "
              "(Gilligan and Noddings).", "care_ethics_response"),
    Framework("virtue_ethics", "Virtue Ethics & Sage Council", prompts.VIRTUE_ETHICS_PROMPT,
              "Weighs character: a council of six sages from different traditions votes, guided by "
              "practical wisdom and the golden mean.", "virtue_ethics_response"),
]

_EXTRA: dict[str, Framework] = {}


def register(fw: Framework):
    if "{fenced}" not in fw.prompt:
        raise ValueError(f"framework {fw.key}: prompt must contain {{fenced}}")
    _EXTRA[fw.key] = fw


def _load_entry_points():
    try:
        from importlib.metadata import entry_points
        for ep in entry_points(group="ama.frameworks"):
            try:
                register(ep.load())
            except Exception:
                pass
    except Exception:
        pass


_load_entry_points()


def active() -> list[Framework]:
    wanted = [k.strip() for k in os.environ.get("AMA_EXTRA_FRAMEWORKS", "").split(",") if k.strip()]
    return CORE + [_EXTRA[k] for k in wanted if k in _EXTRA]


def get(key: str) -> Framework | None:
    for fw in CORE + list(_EXTRA.values()):
        if fw.key == key:
            return fw
    return None
