# Changes

## 3.0.1 (2026-11-02)

- **Delete from the review queue.** Each entry in *Submitted Moral Dilemmas* now has a **Delete** button.
  The first click asks for confirmation, and the second permanently removes the dilemma, its analysis and
  its search vector. It works for pending and evaluated entries and is available to signed-in admins only.
  - API: `DELETE /api/v1/submissions/{id}` (also `/api/v1/dilemmas/{id}` and the 2.x path
    `/api/submissions/{id}`).
- **Gemini key help** now follows Google AI Studio's current steps ("Get API key", then "Create API key"),
  with notes on cost, limits and free-tier privacy, plus a link to a video guide.

## 3.0.0 (2026-11-02): first open-source release

ArtificialMoralAgent is now an installable package (`pip install artificialmoralagent`), licensed under
Apache-2.0. Its ethical reasoning is unchanged from 2.x: the same four frameworks, the sage council and the
weighted conviction blend.

### New
- **Installs anywhere.** One command, `ama`, on Windows, macOS and Linux. `ama init` walks you through setup,
  `ama doctor` checks it, and `ama serve` runs it.
- **No database to set up.** The default is SQLite with sqlite-vec vector search in `~/.ama`. Postgres with
  pgvector is optional, and AMA works with an existing 2.x `dilemmas` table.
- **Any model provider** via LiteLLM: Gemini, Claude, OpenAI-compatible servers, and local Ollama. You can
  choose a different model for each stage.
  - Presets: `cloud-cheap` (the default, Gemini Flash-Lite), `cloud-quality` and `local`.
  - A step-by-step guide to a free Gemini key is in the CLI, at `/help/gemini-key` and in `docs/gemini-key.md`.
- **REST API v1** (`/api/v1/...`): evaluations (with streaming via `?stream=true`), triage, quick check,
  search, frameworks, feedback, review queue and publishing. API keys are hashed at rest. The 2.x routes
  still work.
- **MCP server** (`ama mcp`, or `ama serve --mcp`):
  - Tools: `evaluate_dilemma`, `quick_check`, `compare_options`, `explain_framework` and
    `search_precedents`.
  - Resources and prompt templates.
- **Public demo mode.**
  - Visitors can run evaluations on the host's key, within limits: per IP per day, per day overall, and a
    daily USD budget.
  - Above those limits, their dilemmas wait in the review queue.
  - Demo results are private until an admin publishes them.
- **Time-limited public knowledge base.** `AMA_KB_PUBLIC_UNTIL` sets the date until which visitors can
  browse published dilemmas.
- **`ama db export` / `ama db import`** moves data between SQLite and Postgres, and from 2.x installations.
- **Framework plug-ins** via the `ama.frameworks` entry point.
- **Evaluation set**: 24 reference dilemmas and a runner script (`evalset/`).
- **Docs, white paper, Docker image and CI.** CI covers 3 operating systems, Postgres and secret scanning.

### Safety (always on)
- **Safety triage runs before every analysis and cannot be turned off.**
  - If the triage model fails, a keyword check runs instead, rather than letting the request through.
  - A crisis gets support resources, not an analysis.
- The disclaimer is attached to every response, in the web app, the API and MCP.
- User text is fenced inside `<dilemma>` tags, so instructions hidden in a dilemma are treated as content.
- Input length limits apply, and per-minute rate limits apply to every caller.

### Security
- There is no default password. Admin passwords are hashed with scrypt and must be 10+ characters.
- Session cookies are signed. A random secret is generated per installation and stored in `~/.ama/secret`.
- AMA listens only on 127.0.0.1 by default. CORS is off unless `AMA_CORS_ORIGINS` is set, and security
  headers are on every response.
- Secrets live only in `~/.ama/.env`, which has mode 0600 on Unix and is never read from the project folder.

### Upgrading from 2.x
See `docs/upgrading.md`. In short:
1. Point `AMA_DATABASE_URL` at your old database and run `ama db export --published-only -o curated.jsonl`.
2. Clear `AMA_DATABASE_URL` (or point it at the new database) and run `ama db import curated.jsonl --publish`.
3. Create an admin account with `ama user add admin`. The 2.x default password no longer exists.

### Dependency note
`mcp` is pinned below 2.0. MCP SDK 2.x renamed the FastMCP API, and support for it will come in a later
release.
