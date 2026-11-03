# Models

Every call goes through [LiteLLM](https://docs.litellm.ai), so one string chooses the provider.

| Preset (`ama init`) | Models | Keys |
|---|---|---|
| `cloud-cheap` (default) | `gemini/gemini-3.5-flash-lite`, embeddings `gemini/gemini-embedding-001` (768) | `GEMINI_API_KEY` (free tier available) |
| `cloud-quality` | Gemini Flash for frameworks, `anthropic/claude-sonnet-5-5` as arbiter | Gemini + Anthropic |
| `local` | `ollama_chat/gemma4:12b-it-qat`, embeddings `ollama/nomic-embed-text` (768) | none, runs on your machine |

You can set a model per stage: `AMA_TRIAGE_MODEL`, `AMA_FRAMEWORK_MODEL` and `AMA_ARBITER_MODEL`. Signed-in
users and API keys may choose from `AMA_ALLOWED_MODELS`; guests always get `AMA_MODEL`.

**Embeddings.** The vector size (`AMA_EMBED_DIM`, default 768) is fixed per database. If you change the
embedding model to one with a different size, start a new database, or export the dilemmas and import them
into a fresh one. Search then covers the newly evaluated dilemmas.

Every evaluation records its model, prompt version, tokens, cost and duration. The AMA 2.x benchmark
results are in `docs/benchmarks/benchmark_results.json`.
