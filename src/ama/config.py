"""
Settings for ArtificialMoralAgent.

Everything comes from environment variables, optionally loaded from `$AMA_HOME/.env`
(default `~/.ama/.env`, written by `ama init`). Nothing is read from any other project's files.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

AMA_HOME = Path(os.environ.get("AMA_HOME", Path.home() / ".ama")).expanduser()
ENV_FILE = AMA_HOME / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=False)


def _s(k, d=""):
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else v.strip()


def _i(k, d):
    try:
        return int(float(_s(k, str(d))))
    except ValueError:
        return d


def _f(k, d):
    try:
        return float(_s(k, str(d)))
    except ValueError:
        return d


def _b(k, d=False):
    return _s(k, "true" if d else "false").lower() in ("1", "true", "yes", "on")


# Presets chosen in `ama init`. Model strings are LiteLLM strings.
PRESETS = {
    "cloud-cheap": {"AMA_MODEL": "gemini/gemini-3.5-flash-lite", "AMA_EMBED_MODEL": "gemini/gemini-embedding-001"},
    "cloud-quality": {"AMA_MODEL": "gemini/gemini-3.8-flash", "AMA_ARBITER_MODEL": "anthropic/claude-sonnet-5-5",
                      "AMA_EMBED_MODEL": "gemini/gemini-embedding-001"},
    "local": {"AMA_MODEL": "ollama_chat/gemma4:12b-it-qat", "AMA_EMBED_MODEL": "ollama/nomic-embed-text"},
}
DEFAULT_MODEL = PRESETS["cloud-cheap"]["AMA_MODEL"]


@dataclass
class Settings:
    home: Path = AMA_HOME
    database_url: str = field(default_factory=lambda: _s("AMA_DATABASE_URL", ""))       # blank = SQLite in AMA_HOME
    model: str = field(default_factory=lambda: _s("AMA_MODEL", DEFAULT_MODEL))
    triage_model: str = field(default_factory=lambda: _s("AMA_TRIAGE_MODEL", ""))         # blank = model
    framework_model: str = field(default_factory=lambda: _s("AMA_FRAMEWORK_MODEL", ""))   # blank = model
    arbiter_model: str = field(default_factory=lambda: _s("AMA_ARBITER_MODEL", ""))       # blank = model
    embed_model: str = field(default_factory=lambda: _s("AMA_EMBED_MODEL", "gemini/gemini-embedding-001"))
    embed_dim: int = field(default_factory=lambda: _i("AMA_EMBED_DIM", 768))
    allowed_models: list = field(default_factory=lambda: [m.strip() for m in _s(
        "AMA_ALLOWED_MODELS", "gemini/gemini-3.5-flash-lite,gemini/gemini-3.8-flash,anthropic/claude-haiku-5-5,"
        "anthropic/claude-sonnet-5-5,ollama_chat/gemma4:12b-it-qat").split(",") if m.strip()])
    ollama_base_url: str = field(default_factory=lambda: _s("OLLAMA_BASE_URL", "http://localhost:11434"))
    host: str = field(default_factory=lambda: _s("AMA_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _i("AMA_PORT", 8410))
    root_path: str = field(default_factory=lambda: _s("AMA_ROOT_PATH", ""))               # behind a reverse proxy subpath
    cors_origins: list = field(default_factory=lambda: [o.strip() for o in _s("AMA_CORS_ORIGINS", "").split(",") if o.strip()])
    secret: str = field(default_factory=lambda: _s("AMA_SECRET", ""))
    max_chars: int = field(default_factory=lambda: _i("AMA_MAX_DILEMMA_CHARS", 4000))
    request_timeout: int = field(default_factory=lambda: _i("AMA_REQUEST_TIMEOUT", 90))
    # Public demo: guests get full evaluations on the owner's key, within these limits
    public_demo: bool = field(default_factory=lambda: _b("AMA_PUBLIC_DEMO", False))
    demo_per_ip_per_day: int = field(default_factory=lambda: _i("AMA_DEMO_PER_IP_PER_DAY", 5))
    demo_per_day: int = field(default_factory=lambda: _i("AMA_DEMO_PER_DAY", 200))
    demo_budget_usd_per_day: float = field(default_factory=lambda: _f("AMA_DEMO_BUDGET_USD_PER_DAY", 2.0))
    # Public knowledge base: evaluated dilemmas are browsable by guests until this date (blank = always, "off" = never)
    kb_public_until: str = field(default_factory=lambda: _s("AMA_KB_PUBLIC_UNTIL", ""))
    rate_per_minute: int = field(default_factory=lambda: _i("AMA_RATE_PER_MINUTE", 30))
    fake_llm: bool = field(default_factory=lambda: _b("AMA_FAKE_LLM", False))         # tests / CI: canned answers

    def stage_model(self, stage: str) -> str:
        return {"triage": self.triage_model, "framework": self.framework_model,
                "arbiter": self.arbiter_model}.get(stage) or self.model

    @property
    def sqlite_path(self) -> Path:
        return self.home / "ama.db"

    @property
    def effective_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.sqlite_path}"

    def ensure_secret(self) -> str:
        """A per-install signing secret, kept in AMA_HOME/secret (never in the repo)."""
        if self.secret:
            return self.secret
        f = self.home / "secret"
        self.home.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text(secrets.token_hex(32), encoding="utf-8")
            try:
                os.chmod(f, 0o600)
            except OSError:
                pass
        self.secret = f.read_text(encoding="utf-8").strip()
        return self.secret


_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    global _settings
    if _settings is None or reload:
        _settings = Settings()
    return _settings


def has_cloud_key(model: str) -> bool:
    if model.startswith("gemini/"):
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    if model.startswith("anthropic/"):
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if model.startswith("openai/"):
        return bool(os.environ.get("OPENAI_API_KEY"))
    return True   # local
