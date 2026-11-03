# Contributing

Thank you for helping. Ways to contribute:
- **A new ethical framework:** see [docs/frameworks.md](docs/frameworks.md). This is a good first contribution.
- **Evaluation cases:** add JSON lines to `evalset/dilemmas.jsonl` (`id`, `title`, `dilemma`, `tension`).
- **Fixes, docs, translations.**

Development:
```bash
git clone https://github.com/tgreenhaw5/ArtificialMoralAgent && cd ArtificialMoralAgent
pip install -e ".[dev,postgres]"
pre-commit install
AMA_FAKE_LLM=true pytest -q          # tests use a stand-in model: no keys, no network
ruff check src tests
```

Please keep these guarantees when you change things:
- Safety triage always runs first, and its local backstop stays.
- The disclaimer appears on every result.
- User text is always fenced in prompts.

If you change a prompt, bump `PROMPT_VERSION` in `src/ama/prompts.py`. By contributing you agree your
work is licensed under Apache-2.0. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
