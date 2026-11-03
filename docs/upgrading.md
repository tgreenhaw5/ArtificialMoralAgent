# Upgrading from AMA 2.x

1. **Install:** `pipx install artificialmoralagent`, then run `ama init` (choose your preset and create the
   admin login).
2. **Bring your knowledge base:** either point AMA at the old database directly (`AMA_DATABASE_URL=…/moral_agent_db`;
   it adds the columns it needs and keeps your data), or export and import:
   ```bash
   AMA_DATABASE_URL=postgresql://…/moral_agent_db ama db export --published-only -o curated.jsonl
   ama db import curated.jsonl --publish
   ```
3. **What changed:**
   - **Login:** a single shared password is replaced by user accounts (`ama user add NAME`). The old UI's
     password-only login still works while there is exactly one admin.
   - **Model names:** these are now LiteLLM strings (`gemini/gemini-3.5-flash-lite`). Old names such as
     `gemini-3.5-flash-lite` and `claude-sonnet-5-5` are accepted and converted.
   - **Settings:** AMA reads `~/.ama/.env` only, never another project's `.env`.
   - **Models allowed:** only models in `AMA_ALLOWED_MODELS` can be requested.
   - **CORS:** it's off by default, where it used to allow every origin. Set `AMA_CORS_ORIGINS` if needed.
   - **API:** there is a new versioned API at `/api/v1`, plus an MCP server, streaming, API keys and the public demo mode.
