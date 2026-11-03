from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

JSON_FIELDS = ("utilitarian_response", "deontology_response", "virtue_ethics_response", "care_ethics_response",
               "verdict", "extra")
PUBLIC_FIELDS = ("id", "dilemma_text", *JSON_FIELDS, "status", "model_details", "prompt_version",
                 "thumbs_up_down", "created_at", "published", "source")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def record_from_analysis(text: str, analysis: dict, status="done", published=True, source="evaluated") -> dict:
    return {
        "id": new_id(), "dilemma_text": text,
        "utilitarian_response": analysis.get("utilitarian"), "deontology_response": analysis.get("deontology"),
        "virtue_ethics_response": analysis.get("virtue_ethics"), "care_ethics_response": analysis.get("care_ethics"),
        "verdict": analysis.get("verdict"), "extra": {"extra_frameworks": analysis.get("extra_frameworks") or {},
                                                      "triage": analysis.get("triage")},
        "embedding": analysis.get("embedding"), "status": status, "model_details": analysis.get("model_details"),
        "prompt_version": analysis.get("prompt_version"), "thumbs_up_down": None, "created_at": now_iso(),
        "published": published, "source": source,
    }


def public(rec: dict | None) -> dict | None:
    if rec is None:
        return None
    out = {k: rec.get(k) for k in PUBLIC_FIELDS}
    for k in JSON_FIELDS:
        if isinstance(out.get(k), str):
            try:
                out[k] = json.loads(out[k])
            except Exception:
                pass
    out["published"] = bool(out.get("published"))
    out["status"] = out.get("status") or "done"
    return out


class Store(ABC):
    backend = "?"

    @abstractmethod
    def init(self): ...

    # dilemmas
    @abstractmethod
    def add(self, rec: dict) -> dict: ...
    @abstractmethod
    def update(self, dilemma_id: str, fields: dict) -> dict | None: ...
    @abstractmethod
    def get(self, dilemma_id: str) -> dict | None: ...
    @abstractmethod
    def list(self, status: str | None = "done", published_only=False, limit=25, offset=0) -> list[dict]: ...
    @abstractmethod
    def find_exact(self, text: str, model: str) -> dict | None: ...
    @abstractmethod
    def similar(self, vec: list[float], k=6, model: str | None = None, published_only=False) -> list[tuple[dict, float]]: ...
    @abstractmethod
    def delete(self, dilemma_id: str) -> bool: ...
    @abstractmethod
    def count(self) -> dict: ...
    @abstractmethod
    def export_all(self) -> list[dict]:
        """Every dilemma with its embedding (for `ama db export`)."""

    # accounts & keys
    @abstractmethod
    def put_user(self, name: str, pw_hash: str, role: str = "admin"): ...
    @abstractmethod
    def get_user(self, name: str) -> dict | None: ...
    @abstractmethod
    def list_users(self) -> list[dict]: ...
    @abstractmethod
    def add_key(self, key_id: str, key_hash: str, label: str, owner: str): ...
    @abstractmethod
    def key_by_hash(self, key_hash: str) -> dict | None: ...
    @abstractmethod
    def list_keys(self) -> list[dict]: ...
    @abstractmethod
    def revoke_key(self, key_id: str) -> bool: ...

    # usage (public demo limits and spend)
    @abstractmethod
    def log_usage(self, day: str, who: str, kind: str, cost: float): ...
    @abstractmethod
    def usage_day(self, day: str, who: str | None = None, kind: str | None = None) -> tuple[int, float]: ...
