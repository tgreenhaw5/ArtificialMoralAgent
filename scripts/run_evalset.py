"""Run the evaluation set against a model and write one JSON line per case (verdict summary, convictions, cost)."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ama import engine


async def main(a):
    cases = [json.loads(l) for l in Path(a.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.limit:
        cases = cases[: a.limit]
    with open(a.out, "w", encoding="utf-8") as f:
        for c in cases:
            t0 = time.time()
            try:
                r = await engine.evaluate(c["dilemma"], a.model)
                v = r.get("verdict") or {}
                row = {"id": c["id"], "model": a.model, "crisis": r.get("is_crisis", False),
                       "alignment": v.get("alignment_status"), "majority": (v.get("majority_response") or {}).get("action"),
                       "convictions": {k: (x or {}).get("weight") for k, x in (v.get("framework_convictions") or {}).items()},
                       "dissent": len(v.get("dissenting_perspectives") or []), "usage": r.get("usage")}
            except Exception as e:
                row = {"id": c["id"], "model": a.model, "error": str(e)[:300]}
            row["seconds"] = round(time.time() - t0, 1)
            f.write(json.dumps(row) + "\n")
            print(row["id"], row.get("alignment") or row.get("error"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cases", default=str(Path(__file__).resolve().parent.parent / "evalset" / "dilemmas.jsonl"))
    ap.add_argument("--out", default="evalset-results.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    asyncio.run(main(ap.parse_args()))
