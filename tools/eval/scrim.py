"""Practice matches on the platform: queue a five-match unranked group against a team and report it.

usage: python scrim.py TEAM_ID map1,map2,map3,map4,map5   queue a group (spends shared team quota), wait, report
       python scrim.py --group GROUP_ID                     report an existing group
The platform plays our current submission, so submit the version under test first.
Summaries are saved to work/platform/scrim/.
"""

import json
import os
import re
import subprocess
import sys
import time

S = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(S, "work", "platform", "scrim")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
ME = "51e8da36-33a4-4c41-9775-6c463886d003"


def cambc(*args):
    p = subprocess.run(["cambc", *args], capture_output=True, text=True, timeout=300)
    return p.stdout + p.stderr


def walk(o):
    """Every (key, value) pair in a JSON tree."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def group_matches(group):
    """[(match id, status, map, our side 'teamA'/'teamB')] for a practice group."""
    text = cambc("match-groups", "show", group, "--json")
    try:
        data = json.loads(text)
    except ValueError:
        return None, text
    matches = []
    for m in data.get("matches", []):
        side = next(
            ("team" + t["side"].upper() for t in m["teams"] if t["teamId"] == ME), None
        )
        matches.append((m["matchId"], m["status"], m["map"], side))
    return data, matches


def report(group):
    os.makedirs(OUT, exist_ok=True)
    while True:
        data, matches = group_matches(group)
        if data is None:
            print("unexpected output:", matches[:500])
            return
        pending = [
            m for m in matches if m[1] not in ("finished", "failed", "cancelled")
        ]
        if matches and not pending:
            break
        print(
            f"{time.strftime('%H:%M:%S')} waiting: {len(pending)} of {len(matches)} pending",
            flush=True,
        )
        time.sleep(30)
    wins = 0
    for mid, status, mapname, side in matches:
        path = os.path.join(OUT, mid + ".json")
        if not os.path.exists(path):
            cambc("matches", "summary", mid, "--json", "--output", path)
        try:
            with open(path) as f:
                d = json.load(f)
        except (OSError, ValueError):
            print(f"{mapname:12s} {status} (no summary)")
            continue
        gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        other = "teamB" if side == "teamA" else "teamA"
        won = d["match"]["outcome"] == side
        wins += won
        deaths = {
            t: sum(
                int(c["metrics"]["deaths"]) for c in d["champions"] if c["team"] == t
            )
            for t in (side, other)
        }
        print(
            f"{mapname:12s} {'WIN ' if won else 'loss'} r{d['match']['roundsCompleted']:4d} "
            f"gems {gems.get(side, 0):4d}-{gems.get(other, 0):4d} deaths {deaths[side]:2d}-{deaths[other]:2d} "
            f"(we were {side})"
        )
    print(f"group {group}: {wins}/{len(matches)}")


def main():
    if sys.argv[1:2] == ["--group"]:
        report(sys.argv[2])
        return
    team, maps = sys.argv[1], sys.argv[2]
    text = cambc("match-groups", "create", team, "--maps", maps, "--json")
    print(text[:800])
    try:
        data = json.loads(text)
        group = data.get("groupId") or data.get("id")
        groups = [group] if UUID.fullmatch(str(group or "")) else []
    except (ValueError, AttributeError):
        groups = []
    if not groups:
        return
    report(groups[0])


if __name__ == "__main__":
    main()
