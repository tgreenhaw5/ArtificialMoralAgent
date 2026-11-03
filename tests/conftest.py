import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ["AMA_FAKE_LLM"] = "true"


@pytest.fixture()
def ama_env(tmp_path, monkeypatch):
    """A fresh install in a temp AMA_HOME with the fake model; returns a function to (re)build the app."""
    monkeypatch.setenv("AMA_HOME", str(tmp_path))
    monkeypatch.setenv("AMA_FAKE_LLM", "true")
    for k in ("AMA_DATABASE_URL", "AMA_PUBLIC_DEMO", "AMA_KB_PUBLIC_UNTIL", "AMA_RATE_PER_MINUTE"):
        monkeypatch.delenv(k, raising=False)
    import ama.config as cfg
    monkeypatch.setattr(cfg, "AMA_HOME", tmp_path)

    def build(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        s = cfg.get_settings(reload=True)
        s.home = tmp_path
        from ama import security
        from ama.store import get_store
        get_store(reload=True)
        security._hits.clear()
        from ama.api import create_app
        return create_app()
    return build
