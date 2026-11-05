# MCP server

```bash
ama mcp                       # stdio, for local assistants
ama mcp --http --port 8411    # Streamable HTTP on this computer only (127.0.0.1), no key needed
ama serve --mcp               # web app + MCP at /mcp on the same port, API key required
```

**MCP over the network needs an API key.** Every MCP call runs on the host's model key, so `ama serve --mcp`
accepts MCP requests at `/mcp` only with an AMA API key, and applies the same per-minute rate limit as the
REST API. Create a key with `ama keys create my-agent` and send it as a header:

```json
{ "mcpServers": { "ama": { "type": "http", "url": "https://ama.example.com/mcp",
                           "headers": { "Authorization": "Bearer ama_xxxx_…" } } } }
```

`ama mcp --http` has no key check, so it stays bound to 127.0.0.1 for use on the same computer. For anything
reachable from other machines (Docker, a server, a reverse proxy), use `ama serve --mcp`.

Client configuration (Claude Desktop, Claude Code, Cursor, VS Code):
```json
{ "mcpServers": { "ama": { "command": "ama", "args": ["mcp"] } } }
```
Without a permanent install: `{"command": "uvx", "args": ["--from", "artificialmoralagent", "ama", "mcp"]}`.

| Tool | Use |
|---|---|
| `evaluate_dilemma(dilemma, depth="full" or "quick")` | Full four-framework analysis + verdict |
| `quick_check(action, context)` | Fast "should I proceed?" before a consequential action |
| `compare_options(situation, options[])` | Rank 2–5 candidate actions across the frameworks |
| `explain_framework(name)` | What a framework weighs |
| `search_precedents(query, k)` | Similar dilemmas already evaluated |

Resources: `ama://frameworks`, `ama://evaluations/{id}`. Prompts: `ethics_review`, `stakeholder_check`.
The tool descriptions tell agents to present results as perspectives for a human to weigh, not as orders.
Crisis situations return support resources.
