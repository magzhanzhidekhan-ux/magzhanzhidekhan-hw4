import json

QS = ["Q-09", "Q-03", "Q-08", "Q-13", "Q-18"]

def stats(path):
    d = json.load(open(path, encoding="utf-8"))
    calls = [c for r in d["log"] for c in r.get("tool_calls", [])]
    lk = [c["arguments"] for c in calls if c["tool"] == "lookup"]
    errs = sum(1 for c in calls if "error" in c["result"])
    return d["rounds"], len(calls), len(lk), errs, d["in"], d["out"], d["parsed"]

print("q | rounds calls lookups errors in out parsed")
for q in QS:
    for label, folder in (("mine ", "run1"), ("vague", "runc1_vague")):
        print(q, label, stats(f"outputs/{folder}/logs/{q}.json"))