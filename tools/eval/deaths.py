"""Death timeline for one platform match summary: who died, when, where, killed by what.

usage: python deaths.py SUMMARY.json   (from `cambc matches summary <id> --json -o SUMMARY.json`)
Our side is found by the draft: v6+ opens Cassi & Issac, then Stellar.
"""

import json
import sys

with open(sys.argv[1]) as f:
    d = json.load(f)
picks = {
    t: [p["champion"] for p in d["roster"]["draft"] if p["team"] == t]
    for t in ("teamA", "teamB")
}
ours = next(
    t for t in picks if picks[t][:1] == ["Cassi & Issac"] and "Stellar" in picks[t][:2]
)
print(
    "we are",
    ours,
    picks[ours],
    "| rounds",
    d["match"]["roundsCompleted"],
    "| outcome",
    d["match"]["outcome"],
)
rows = []
for e in d["events"]:
    if e["kind"] != "death":
        continue
    o = e["owner"]
    for en in e["entries"]:
        t = en.get("target") or {}
        killer = (
            f"{t.get('name')}({'us' if t.get('team') == ours else 'them'})"
            if t.get("kind") == "champion"
            else (t.get("kind") or en.get("context"))
        )
        rows.append(
            (
                en["timestamp"]["round"],
                "US  " if o["team"] == ours else "THEM",
                o["name"],
                killer,
                en.get("x"),
                en.get("y"),
            )
        )
rows.sort()
gl = {}
for e in d["events"]:
    if e["kind"] == "gemLoss" and e["owner"]["team"] == ours:
        for en in e["entries"]:
            gl[(en["timestamp"]["round"], e["owner"]["name"])] = en.get("value")
for r in rows:
    lost = gl.get((r[0], r[2]), "")
    print(
        f"r{r[0]:4d} {r[1]} {r[2]:8s} killed by {r[3]:16s} at ({r[4]},{r[5]}) {'lost ' + str(lost) + ' gems' if lost else ''}"
    )
