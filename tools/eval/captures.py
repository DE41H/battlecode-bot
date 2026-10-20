"""Per-champion capture counts and gems from kept statistics JSONs: python captures.py FILE.json..."""
import json, sys
for path in sys.argv[1:]:
    d = json.load(open(path))
    names = {r["id"]: (r["team"], r["name"]) for r in d["roster"]["champions"]}
    caps = {}
    for e in d["events"]:
        if e["kind"] == "gemCollection":
            k = (e["owner"]["team"], e["owner"]["name"])
            caps[k] = (len(e["entries"]), sum(int(en.get("value") or 0) for en in e["entries"]))
    deaths = {names[c["id"]]: int(c["metrics"]["deaths"]) for c in d["champions"]}
    print(path.rsplit("/", 1)[-1], d["match"]["roundsCompleted"])
    for team in ("teamA", "teamB"):
        print("  ", team, "  ".join(f"{n[:6]}:{caps.get((t, n), (0, 0))[0]}c/{caps.get((t, n), (0, 0))[1]}g/{deaths[(t, n)]}d" for (t, n) in names.values() if t == team))
