# Evaluation set

`dilemmas.jsonl`: classic and modern cases chosen because the frameworks are expected to pull in different
directions (`tension` says how). Use them to compare models and prompt versions:

```bash
python scripts/run_evalset.py --model gemini/gemini-3.5-flash-lite --out results-flashlite.jsonl
```

Each case records the arbiter's alignment status, the majority action, each framework's conviction, and
tokens, cost and time. Contributions are welcome: add a line with `id`, `title`, `dilemma` and `tension`.
