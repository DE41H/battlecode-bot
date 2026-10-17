"""Run bot X against one or more opponents on every map, both sides, as a single cambc run-batch.

usage: python evalbots.py X OPP [OPP...] [--jobs N] [--maps a,b] [--keep]
Bots are dirs (paths) or names under bots/. Prints one RES line and one readable line per game,
a summary per opponent and an overall TOTAL line.

Speed: a match costs ~1 s of CPU, but the runner rebuilds each bot (~18 s CPU) and JIT-compiles
its 41 MB wasm module (~20 s CPU) every time. One batch builds each bot once, and the wasmtime
cache (CAMBC_WASMTIME_CACHE) makes compiles after the first free, so a 102-game pool takes about
a minute instead of twenty.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

S = os.path.dirname(os.path.abspath(__file__))
R = os.path.dirname(os.path.dirname(S))
WORK = os.path.join(S, "work")


def resolve(bot):
    return os.path.abspath(bot) if "/" in bot else os.path.join(R, "bots", bot)


def stage(bots, root):
    """Copy each bot's source to its own dir: concurrent runs never share (or race on) a build dir."""
    staged = {}
    for bot in bots:
        name = os.path.basename(bot.rstrip("/"))
        dst = os.path.join(root, name)
        if dst in staged.values():
            dst = os.path.join(root, f"{name}-{len(staged)}")
        shutil.copytree(os.path.join(bot, "src"), os.path.join(dst, "src"))
        staged[bot] = dst
    return staged


def summarize(path):
    """Compact per-game record from a --statistics JSON export."""
    with open(path) as f:
        d = json.load(f)
    teams = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
    side = {"teamA": "A", "teamB": "B"}
    per = {
        "A": dict(kills=0, deaths=0, gold=0, draft=[]),
        "B": dict(kills=0, deaths=0, gold=0, draft=[]),
    }
    for c in d["champions"]:
        s, m = side[c["team"]], c["metrics"]
        per[s]["kills"] += int(m["kills"])
        per[s]["gold"] += int(m["earnedGold"])
        per[s]["deaths"] += int(m["deaths"])
    for pick in d["roster"]["draft"]:
        per[side[pick["team"]]]["draft"].append(pick["champion"])
    faults = d.get("diagnostics", {}).get("botFaults", {})
    for t, s in side.items():
        per[s]["gems"] = teams[t]
        per[s]["crashes"] = int(faults.get(t, 0))
    outcome = d["match"]["outcome"]
    return dict(winner=side.get(outcome), round=d["match"]["roundsCompleted"], rows=per)


def run_batch(jobs, out, n_jobs, release):
    manifest = os.path.join(out, "manifest.txt")
    with open(manifest, "w") as f:
        for j in jobs:
            f.write(
                f"{j['a']} {j['b']} {j['map']} {j['replay']} --statistics {j['stats']} --json\n"
            )
    cmd = ["cambc", "run-batch", manifest, "--jobs", str(n_jobs), "--color", "never"]
    if release:
        cmd.append("--release")
    p = subprocess.run(cmd, cwd=R, capture_output=True, text=True)
    return p.stdout + p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("x")
    ap.add_argument("opps", nargs="+")
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS", 10)))
    ap.add_argument("--maps", default="")
    ap.add_argument("--keep", action="store_true", help="keep replays and statistics")
    ap.add_argument("--debug-mode", action="store_true", help="run without --release")
    args = ap.parse_args()
    os.environ.setdefault("CAMBC_WASMTIME_CACHE", os.path.join(WORK, "wtcache"))
    mapdir = os.environ.get("MAPDIR", os.path.join(R, "maps"))
    maps = (
        args.maps.split(",")
        if args.maps
        else sorted(f[:-7] for f in os.listdir(mapdir) if f.endswith(".map26a"))
    )
    x = resolve(args.x)
    opps = [resolve(o) for o in args.opps]
    t0 = time.time()
    out = os.path.join(WORK, "batch", f"{os.path.basename(x)}-{os.getpid()}-{int(t0)}")
    os.makedirs(out)
    staged = stage([x, *opps], os.path.join(out, "bots"))
    jobs = []
    for o in opps:
        oname = os.path.basename(o)
        for m in maps:
            mp = os.path.join(mapdir, m + ".map26a")
            for side in "AB":
                a, b = (staged[x], staged[o]) if side == "A" else (staged[o], staged[x])
                tag = f"{oname}-{m}-x{side}"
                jobs.append(
                    dict(
                        opp=oname,
                        map=mp,
                        mapname=m,
                        side=side,
                        a=a,
                        b=b,
                        replay=os.path.join(out, tag + ".repl26a"),
                        stats=os.path.join(out, tag + ".json"),
                    )
                )
    log = run_batch(jobs, out, args.jobs, not args.debug_mode)
    # Retry anything that failed (infrastructure hiccups), once, in a second batch.
    missing = [j for j in jobs if not os.path.exists(j["stats"])]
    if missing:
        for j in missing:
            for k in ("replay", "stats"):
                if os.path.exists(j[k]):
                    os.remove(j[k])
        log += run_batch(
            missing, out, min(args.jobs, len(missing)), not args.debug_mode
        )

    results = []
    for j in jobs:
        r = dict(opp=j["opp"], map=j["mapname"], xside=j["side"])
        try:
            r.update(summarize(j["stats"]))
        except (OSError, ValueError, KeyError) as error:
            r["error"] = repr(error)
        results.append(r)
    with open(os.path.join(WORK, "results.jsonl"), "a") as f:
        for r in results:
            f.write(json.dumps(dict(x=os.path.basename(x), time=int(t0), **r)) + "\n")

    totals = {}
    for r in results:
        s = r["xside"]
        o = "B" if s == "A" else "A"
        if "error" in r:
            print(f"{r['map']:12s} X={s} ERROR {r['error']} vs {r['opp']}")
            continue
        rx, ry = r["rows"][s], r["rows"][o]
        won = r["winner"] == s
        t = totals.setdefault(r["opp"], [0, 0, 0, 0, 0, 0])
        t[0] += won
        t[1] += 1
        t[2] += rx["gems"]
        t[3] += ry["gems"]
        t[4] += rx["kills"]
        t[5] += ry["kills"]
        print(
            f"RES {r['map']} {s} {int(won)} {rx['gems']} {ry['gems']} {r['round']} {rx['kills']} {ry['kills']} {r['opp']}"
        )
        print(
            f"{r['map']:12s} X={s} {'WIN ' if won else 'loss'} r{r['round']:4d}  "
            f"gems {rx['gems']:4d}-{ry['gems']:4d}  kills {rx['kills']:2d}-{ry['kills']:2d}  "
            f"deaths {rx['deaths']:2d}-{ry['deaths']:2d}  gold {rx['gold']:5d}-{ry['gold']:5d}  "
            f"crash {rx['crashes']}/{ry['crashes']}  vs {r['opp']}  [{', '.join(rx['draft'])}]"
        )
    print()
    for opp, (w, n, gx, gy, kx, ky) in totals.items():
        print(
            f"vs {opp}: X wins {w}/{n}  gems {gx}-{gy} ({gx - gy:+d})  kills {kx}-{ky}"
        )
    w = sum(t[0] for t in totals.values())
    n = sum(t[1] for t in totals.values())
    diff = sum(t[2] - t[3] for t in totals.values())
    errors = len(results) - n
    print(
        f"TOTAL {os.path.basename(x)}: wins {w}/{n}  gemdiff {diff:+d}"
        + (f"  ERRORS {errors}" if errors else "")
        + f"  ({time.time() - t0:.0f}s)"
    )
    if errors:
        print(log[-3000:], file=sys.stderr)
    if not args.keep:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    main()
