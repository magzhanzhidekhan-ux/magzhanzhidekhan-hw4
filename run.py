import argparse
import json
import statistics
from pathlib import Path

import strategies as S
from tools import build_tools

PRICE_IN_PER_M = 1.0     # TODO: dollars per 1M input tokens from the pricing page
PRICE_OUT_PER_M = 6.0    # TODO: dollars per 1M output tokens

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True, help="label, e.g. 1, 2, c1_vague")
ap.add_argument("--strategies", default="S1,S2,S3")
ap.add_argument("--questions", default="")
ap.add_argument("--vague", action="store_true", help="C1: vague lookup description")
args = ap.parse_args()

qs = json.load(open("data/questions.json", encoding="utf-8"))
if args.questions:
    wanted = set(args.questions.split(","))
    qs = [q for q in qs if q["id"] in wanted]

out = Path("outputs") / f"run{args.run}"
(out / "logs").mkdir(parents=True, exist_ok=True)
tools = build_tools("Looks things up.") if args.vague else S.TOOLS

for name in args.strategies.split(","):
    rows = []
    for q in qs:
        # only the question text goes to the model, never the answer
        r = S.RUN[name](q["question"], tools) if name == "S3" else S.RUN[name](q["question"])
        r["id"] = q["id"]
        r["correct"] = S.is_correct(r["parsed"], q)
        rows.append(r)
        if name == "S3":
            json.dump(r, open(out / "logs" / f"{q['id']}.json", "w", encoding="utf-8"),
                      indent=2, ensure_ascii=False)
        print(name, q["id"], r["parsed"], "OK" if r["correct"] else "WRONG",
              f"{r['sec']:.1f}s", flush=True)
    secs = [r["sec"] for r in rows]
    tin, tout = sum(r["in"] for r in rows), sum(r["out"] for r in rows)
    summary = {
        "run": args.run, "strategy": name, "model": S.MODEL, "temperature_rejected": S.NO_TEMPERATURE,
        "correct": sum(r["correct"] for r in rows), "n": len(rows),
        "unanswered": sum(r["unanswered"] for r in rows),
        "input_tokens": tin, "output_tokens": tout,
        "median_sec": round(statistics.median(secs), 2), "total_sec": round(sum(secs), 1),
        "cost_usd": round(tin / 1e6 * PRICE_IN_PER_M + tout / 1e6 * PRICE_OUT_PER_M, 4)}
    print(json.dumps(summary))
    json.dump({"summary": summary, "rows": rows},
              open(out / f"results_{name}.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)