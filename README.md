# ArtificialMoralAgent

**Structured ethical analysis for hard decisions.** Describe a dilemma. Four ethical frameworks analyse it
in parallel, each giving its recommended action and how strongly it holds that view:
- **utilitarian**: outcomes;
- **deontological**: duties and rights;
- **care ethics**: relationships and vulnerability;
- **virtue ethics**: character, as judged by a council of six sages.

A **Chief Moral Arbiter** then blends them by conviction weight into a plain-English ruling. It shows where
the frameworks agree and keeps the dissenting views.

It runs on your own computer, as a web app, a REST API and an MCP server, so AI agents and assistants can
ask for an ethics check before they act.

> **Decision support, not an authority.** ArtificialMoralAgent shows its reasoning so you can weigh it. It is
> not legal, medical, psychological or other professional advice. Every dilemma passes a safety triage first:
> people in crisis get support resources, not an analysis.

## Quick start (Windows, macOS, Linux)

```bash
pipx install git+https://github.com/tgreenhaw5/ArtificialMoralAgent   # or: uv tool install git+https://…
ama init                               # pick a preset, paste a free Gemini key, create your admin login
ama serve                              # http://localhost:8410  ·  API docs at /docs
```

Once the package is on PyPI, `pipx install artificialmoralagent` works too.

There is no database to set up. AMA stores everything in SQLite with vector search in `~/.ama`. Use
Postgres + pgvector when you serve many people (see [Self-hosting](docs/self-hosting.md)).

**No key yet?** The default model is Google's Gemini Flash-Lite, and a free key takes two minutes:
[how to get one](docs/gemini-key.md). Prefer nothing leaving your machine? Choose the **local** preset with
[Ollama](https://ollama.com).

## Use it from your tools

**MCP** (Claude Desktop, Claude Code, Cursor, VS Code), with `ama` on your PATH:

```json
{ "mcpServers": { "ama": { "command": "ama", "args": ["mcp"] } } }
```

The MCP tools are `evaluate_dilemma`, `quick_check`, `compare_options`, `explain_framework` and
`search_precedents` ([details](docs/mcp.md)).

**REST API**:

```bash
ama keys create my-app                       # prints ama_xxxx_… once
curl -s http://localhost:8410/api/v1/evaluations \
  -H "Authorization: Bearer ama_xxxx_…" -H "Content-Type: application/json" \
  -d '{"dilemma": "My manager asked me to backdate a contract to meet a deadline. Should I comply?"}'
```

Add `?stream=true` to receive each stage as it finishes. See the [API reference](docs/api.md).

## How it works

```
dilemma ─► safety triage ─┬─► utilitarianism ─┐
           (always first)  ├─► deontology      ├─► Chief Moral Arbiter ─► ruling, majority action,
                           ├─► care ethics     │   (weighted conviction     dissenting views, steps
                           └─► virtue council ─┘    blend)
```

- **Any model provider** via LiteLLM: Gemini, Claude, OpenAI-compatible servers, or local Ollama. Each stage
  can use a different model, for example a cheap triage and a strong arbiter.
- **Knowledge base**: evaluated dilemmas are searchable by meaning (vector search), and repeated questions
  are answered from the cache.
- **Extensible**: add an ethical tradition as a plug-in ([Frameworks](docs/frameworks.md)).
- **Read the reasoning**: the [white paper](docs/WHITE_PAPER.md) explains the frameworks and the arbiter.

## Documentation

[Gemini key](docs/gemini-key.md) · [Self-hosting & public demo](docs/self-hosting.md) · [API](docs/api.md) ·
[MCP](docs/mcp.md) · [Models](docs/models.md) · [Frameworks](docs/frameworks.md) ·
[Safety & limitations](docs/safety.md) · [Upgrading from AMA 2.x](docs/upgrading.md)

## Contributing

New ethical frameworks, evaluation cases, translations and fixes are welcome. Start with
[CONTRIBUTING.md](CONTRIBUTING.md). To report a security problem, see [SECURITY.md](SECURITY.md).

Licensed under [Apache-2.0](LICENSE).
