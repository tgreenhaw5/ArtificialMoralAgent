# Self-hosting and the public demo

## One computer (default)
`ama init` then `ama serve`. Data lives in `~/.ama/ama.db` (SQLite with sqlite-vec vector search), and
settings in `~/.ama/.env`. Back up that folder.

## Postgres for a shared server
```bash
pip install "artificialmoralagent[postgres]"
export AMA_DATABASE_URL=postgresql://ama:secret@db-host:5432/ama     # pgvector must be installed on the server
ama doctor && ama serve --host 0.0.0.0
```
If Postgres is configured but unreachable, AMA stops with an error. It never silently switches to SQLite,
because that would split your knowledge base. To move data between backends, use `ama db export` / `ama db import`.

Or use **Docker Compose**: `docker compose up -d` starts AMA and Postgres with pgvector. Add
`--profile local` to include Ollama.

## Behind a reverse proxy (IIS, nginx, Caddy)
- Proxy `https://example.org/ama/` to `http://127.0.0.1:8410/` and set `AMA_ROOT_PATH=/ama`.
- Set `AMA_TRUST_PROXY=true` so per-visitor limits use the real client address (`X-Forwarded-For`).
- Serve over HTTPS. Session cookies are marked `Secure` automatically on HTTPS.
- Leave `AMA_CORS_ORIGINS` empty unless another site's pages must call the API.

## Public demo on your key
Guests can run full evaluations using **your** model key, within limits:

| Setting | Default | Meaning |
|---|---|---|
| `AMA_PUBLIC_DEMO` | `false` | Turn the demo on |
| `AMA_DEMO_PER_IP_PER_DAY` | 5 | Evaluations per visitor per day |
| `AMA_DEMO_PER_DAY` | 200 | Evaluations for all visitors together per day |
| `AMA_DEMO_BUDGET_USD_PER_DAY` | 2.00 | Stop once the day's model spend reaches this |
| `AMA_RATE_PER_MINUTE` | 30 | Requests per client per minute |
| `AMA_MAX_DILEMMA_CHARS` | 4000 | Longest dilemma accepted |

- **Guests always use `AMA_MODEL`.** They can't pick a model.
- **Over a limit**, the dilemma is queued for your review instead, with a message explaining why.
- **Demo results are private:** they don't appear in the public knowledge base until you publish them
  (`POST /api/v1/dilemmas/{id}/publish`).
- **Safety triage and the disclaimers always apply.**

Also set a hard spending limit with your model provider (in Google AI Studio or Cloud billing, for example),
so a mistake in these settings can't run up a bill.

## Knowledge base for a limited time
`AMA_KB_PUBLIC_UNTIL=2027-03-31` lets guests browse and search published dilemmas until that date. After
it, only signed-in users can see them. Leave it blank for always, or set `off` for never.

To publish your curated dilemmas from an existing AMA 2.x database:
```bash
AMA_DATABASE_URL=postgresql://…/moral_agent_db  ama db export --published-only -o curated.jsonl
ama db import curated.jsonl --publish            # into this install's database
```
