import json, glob
for run in ("1", "2"):
    rows = []
    for f in sorted(glob.glob(f"outputs/run{run}/logs/Q-*.json")):
        d = json.load(open(f, encoding="utf-8"))
        calls = sum(len(r.get("tool_calls", [])) for r in d["log"])
        rows.append((d["rounds"], calls, d["id"], d["in"]))
    print("run", run)
    for r in sorted(rows, reverse=True)[:5]:
        print("  rounds=%d calls=%d %s input_tokens=%d" % r)