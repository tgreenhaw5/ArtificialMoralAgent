# MCP server

```bash
ama mcp                       # stdio, for local assistants
ama mcp --http --port 8411    # Streamable HTTP
ama serve --mcp               # web app + MCP at /mcp on the same port
```

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
