"""Tabulate the latest evaluation of each variant from work/results.jsonl.

usage: python summary.py [--opps a,b] [variant...]   (default: every variant seen; opponents of the sweep)
Columns: wins and gem difference per opponent; 'econ' is total rounds to finish vs the starter (lower is faster farming).
"""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
only = None
if args[:1] == ["--opps"]:
    only, args = set(args[1].split(",")), args[2:]
with open(os.path.join(S, "work", "results.jsonl")) as f:
    rows = [json.loads(line) for line in f]
latest = {}
for r in rows:
    key = (r["x"], r["opp"])
    if key not in latest or r["time"] > latest[key][0]["time"]:
        latest[key] = [r]
    elif r["time"] == latest[key][0]["time"]:
        latest[key].append(r)
variants = args or sorted(
    {x for x, _ in latest}, key=lambda x: min(r["time"] for r in rows if r["x"] == x)
)
opps = sorted(only or ({o for _, o in latest} - {"starter-python"}))
print(
    f"{'variant':12s}"
    + "".join(f"{o[:11]:>16s}" for o in opps)
    + f"{'TOTAL':>16s}{'econ':>8s}"
)
for v in variants:
    line, tw, tn, td = f"{v:12s}", 0, 0, 0
    for o in opps:
        games = [g for g in latest.get((v, o), []) if "rows" in g]
        if not games:
            line += f"{'-':>16s}"
            continue
        w = sum(g["winner"] == g["xside"] for g in games)
        d = sum(
            g["rows"][g["xside"]]["gems"]
            - g["rows"]["B" if g["xside"] == "A" else "A"]["gems"]
            for g in games
        )
        tw, tn, td = tw + w, tn + len(games), td + d
        line += f"{w:>4d}/{len(games):<3d}{d:>+8d} "
    line += f"{tw:>4d}/{tn:<3d}{td:>+8d} "
    econ = [g for g in latest.get((v, "starter-python"), []) if "rows" in g]
    line += f"{sum(g['round'] for g in econ):>8d}" if econ else f"{'-':>8s}"
    print(line)
