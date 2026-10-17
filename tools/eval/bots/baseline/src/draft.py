"""Draft: pick a farming composition and split the map into zones, one per pick."""

import math

import cambc
from cambc import game_map
from memory import SHARED, encode_plan

Pick, Team = cambc.ChampionDraft, cambc.Team

# Picks are simultaneous and not exclusive, so this is purely our preferred composition.
PRIORITY = [
    Pick.VENDETTA,
    Pick.CASSI_AND_ISSAC,
    Pick.VARG,
    Pick.RYTH,
    Pick.MARCELLA,
    Pick.TAVI,
    Pick.STELLAR,
    Pick.VESPER_VALE,
    Pick.REN,
    Pick.PRISM,
    Pick.WILLOW,
]


def plan_zones(slots):
    """Assign camp groups to pick slots as angular lanes around our spawn, balanced by gem value."""
    spawn = game_map.spawn_region(Team.ALLY).positions()
    sx = sum(p.x for p in spawn) / len(spawn)
    sy = sum(p.y for p in spawn) / len(spawn)
    groups = game_map.camp_groups()
    zones = [SHARED] * len(groups)
    if slots <= 1:
        return zones

    entries = []
    for group in groups:
        if group.gem_value() <= 0:
            continue
        if any(camp.kind() == cambc.CampType.MONOLITH for camp in group.camps()):
            continue
        tiles = group.spawn_tiles().positions()
        cx = sum(p.x for p in tiles) / len(tiles)
        cy = sum(p.y for p in tiles) / len(tiles)
        entries.append((math.atan2(cy - sy, cx - sx), int(group), group.gem_value()))
    if not entries:
        return zones

    # Rotate the sweep so it starts at the widest angular gap, then cut into equal-value lanes.
    entries.sort()
    gaps = [
        (entries[(i + 1) % len(entries)][0] - entries[i][0]) % (2 * math.pi)
        for i in range(len(entries))
    ]
    start = (gaps.index(max(gaps)) + 1) % len(entries)
    entries = entries[start:] + entries[:start]
    total = sum(gems for _, _, gems in entries)
    running = 0
    for _, index, gems in entries:
        zones[index] = min(slots - 1, int(running * slots / total))
        running += gems
    return zones


def play():
    chosen = cambc.draft.current_draft(Team.ALLY)
    remaining = [pick for pick in PRIORITY if pick not in chosen]
    pick = remaining[0]
    picks = [*chosen, pick]
    team_size = cambc.draft.team_size()

    # Rewrite the plan every pick; the last write is what champions read.
    cambc.draft_memory.submit(encode_plan(picks, plan_zones(team_size)))
    cambc.draft.pick(pick)
