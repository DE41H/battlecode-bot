"""Draft: Tavi Economy composition with champion-aware zone assignment."""

import math

import cambc
from cambc import game_map
from memory import (
    SHARED, PRIO_HIGH, PRIO_NORMAL, PRIO_LOW,
    ROLE_ANCHOR, ROLE_SUPPORT, ROLE_ECON, ROLE_FIGHTER,
    encode_plan,
)

Pick, Team, CampType = cambc.ChampionDraft, cambc.Team, cambc.CampType

# Tavi Economy: used on most maps (open, moderate camp strength).
# Vendetta at slot 2 replaces Willow — data showed Willow contributing only 66 gems
# on rows/3-slot maps while a fighter would produce 250-400.  Willow is pushed to
# last so it only appears on 11-slot teams (impossible in practice).
PRIORITY_ECONOMY = [
    Pick.TAVI,
    Pick.VESPER_VALE,
    Pick.VENDETTA,           # was Willow; Vendetta matches main-bot's top performer
    Pick.VARG,
    Pick.CASSI_AND_ISSAC,
    Pick.RYTH,
    Pick.MARCELLA,
    Pick.STELLAR,
    Pick.REN,
    Pick.PRISM,
    Pick.WILLOW,             # effectively never drafted
]

# Fighter-first: used on high-burst maps (packs, lanes) where Tavi/Willow die
# repeatedly because camp strength overwhelms low-HP champions before they can bank.
PRIORITY_FIGHTER = [
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

# Camp-strength threshold above which we switch to fighter-priority.
# Above this, the average camp group deals enough burst to kill Tavi/Willow
# before they can bank, making the support-healer pairing counterproductive.
_BURST_MAP_THRESHOLD = 90  # average sum-of-strength per group

# Map pick → role constant.
_ROLE_OF = {
    Pick.TAVI:        ROLE_ANCHOR,
    Pick.WILLOW:      ROLE_SUPPORT,
    Pick.VESPER_VALE: ROLE_ECON,
}

# Base banking threshold (gems) per role; stored ÷ 5 to fit in 1 byte.
# Fix 3: lowered ROLE_FIGHTER from 60 → 40; fighters were dying with 50+ gems
# and losing them all (interlock: Issac lost 166 gems in 4 deaths).
_BANK_GEMS = {
    ROLE_ANCHOR:  30,   # Tavi: frequent small banking
    ROLE_SUPPORT: 50,   # Willow: moderate
    ROLE_ECON:    45,   # Vale: moderate (she recalls for gold anyway)
    ROLE_FIGHTER: 40,   # fighters: was 60, lowered to cut gem loss on death
}


def _is_burst_map():
    """Return True when camp strength is high enough that Tavi/Willow die before banking.

    Computes the average total strength per non-monolith group.  Maps like packs
    and lanes have dense, high-strength packs that shred low-HP supports quickly.
    On those maps we run an all-fighter roster instead of Tavi Economy.
    """
    groups = game_map.camp_groups()
    strengths = []
    for g in groups:
        if any(c.kind() == CampType.MONOLITH for c in g.camps()):
            continue
        strengths.append(sum(c.base_stats().base_strength for c in g.camps()))
    if not strengths:
        return False
    return (sum(strengths) / len(strengths)) > _BURST_MAP_THRESHOLD


def _group_priority(group):
    """Assign a priority tier to a camp group."""
    kinds = {camp.kind() for camp in group.camps()}
    if CampType.MONOLITH in kinds or CampType.ELK in kinds:
        return PRIO_HIGH
    if CampType.GOLD_CLUSTER in kinds and CampType.WOLF not in kinds:
        return PRIO_LOW   # pure gold clusters are Vale's specialty; others deprioritise
    return PRIO_NORMAL


def _altar_distance(group, altar_xy):
    """Chebyshev distance from a group's centre to the nearest altar."""
    cx = sum(p.x for p in group.spawn_tiles().positions()) // max(1, group.spawn_tiles().count())
    cy = sum(p.y for p in group.spawn_tiles().positions()) // max(1, group.spawn_tiles().count())
    if not altar_xy:
        return 999
    return min(max(abs(cx - ax), abs(cy - ay)) for ax, ay in altar_xy)


def _gold_ratio(group):
    """Gold value relative to total value — high for gold clusters and wolves."""
    gold = group.gold_value()
    gem  = group.gem_value()
    return gold / (gold + gem + 1)


def plan_zones(picks, team_size):
    """Assign camp groups to champion slots using gem-value-budget allocation.

    Each role is given camps until it holds approximately 1/team_size of the
    map's total gem value (its "budget").  This is map-adaptive: on a map
    dominated by one Elk group, Tavi gets just that group; on a spread-out map
    it may get several small groups.

    Assignment order (Option 2):
      1. Tavi   → highest gem_value / altar_dist score (banking efficiency).
                  Tavi always gets altar-adjacent camps first so it can bank fast.
      2. Vale   → highest gold fraction from remaining (gold passive compounds).
      3. Vendetta → highest raw gem_value from remaining (fastest camp clearer).
      4. Fighters → remaining groups split by angular gem-balanced lanes.

    Monolith groups are always SHARED — fighters respond to the monolith_down
    shared-memory signal instead.
    """
    altars   = game_map.altars().positions()
    altar_xy = [(a.x, a.y) for a in altars]
    groups   = game_map.camp_groups()
    spawn    = game_map.spawn_region(Team.ALLY).positions()
    sx       = sum(p.x for p in spawn) // len(spawn)
    sy       = sum(p.y for p in spawn) // len(spawn)

    # Identify special slots.
    tavi_slot     = next((i for i, p in enumerate(picks) if p == Pick.TAVI),          None)
    vale_slot     = next((i for i, p in enumerate(picks) if p == Pick.VESPER_VALE),   None)
    vendetta_slot = next((i for i, p in enumerate(picks) if p == Pick.VENDETTA),      None)
    # All other picks are generic fighters (Varg, Cassi+Issac, Ryth, Marcella, etc.)
    special = {Pick.TAVI, Pick.VESPER_VALE, Pick.VENDETTA, Pick.WILLOW}
    fighter_slots = [i for i, p in enumerate(picks) if p not in special]

    zones = [SHARED] * len(groups)

    # Collect non-monolith groups with their properties.
    entries = []
    for group in groups:
        if any(camp.kind() == CampType.MONOLITH for camp in group.camps()):
            continue
        tiles = group.spawn_tiles().positions()
        if not tiles:
            continue
        cx = sum(p.x for p in tiles) // len(tiles)
        cy = sum(p.y for p in tiles) // len(tiles)
        altar_dist  = _altar_distance(group, altar_xy)
        gem_value   = group.gem_value()
        gold_value  = group.gold_value()
        entries.append({
            "index":      int(group),
            "cx": cx, "cy": cy,
            "altar_dist": altar_dist,
            "gem_value":  gem_value,
            "gold_value": gold_value,
            "angle":      math.atan2(cy - sy, cx - sx),
            # Pre-computed role scores.
            "score_tavi":     gem_value / max(1, altar_dist),
            "score_vale":     gold_value / max(1, gem_value + gold_value),
            "score_vendetta": gem_value,
        })

    if not entries:
        return zones

    total_gem_value = sum(e["gem_value"] for e in entries) or 1
    budget = total_gem_value / max(1, team_size)

    def _assign(slot, key, n_entries):
        """Greedily assign camps from n_entries to slot until budget filled."""
        if slot is None or not n_entries:
            return
        assigned_value = 0
        for e in n_entries:
            if zones[e["index"]] != SHARED:
                continue
            zones[e["index"]] = slot
            assigned_value += e["gem_value"]
            if assigned_value >= budget:
                break
        # Always assign at least 1 group even if first group exceeds budget.

    # ── 1. Tavi: banking-efficiency score (gem_value / altar_dist) ────────────
    _assign(tavi_slot, "score_tavi",
            sorted(entries, key=lambda e: -e["score_tavi"]))

    # ── 2. Vale: gold-fraction score (gold / total) ───────────────────────────
    _assign(vale_slot, "score_vale",
            sorted(entries, key=lambda e: -e["score_vale"]))

    # ── 3. Vendetta: raw gem value (fastest clearer gets richest remaining) ───
    _assign(vendetta_slot, "score_vendetta",
            sorted(entries, key=lambda e: -e["score_vendetta"]))

    # ── 4. Fighters: angular gem-balanced lanes ───────────────────────────────
    if fighter_slots:
        remaining = [e for e in entries if zones[e["index"]] == SHARED]
        if remaining and len(fighter_slots) > 1:
            remaining.sort(key=lambda e: e["angle"])
            gaps = [
                (remaining[(i + 1) % len(remaining)]["angle"] - remaining[i]["angle"]) % (2 * math.pi)
                for i in range(len(remaining))
            ]
            start = (gaps.index(max(gaps)) + 1) % len(remaining)
            remaining = remaining[start:] + remaining[:start]
            total_remaining = sum(e["gem_value"] for e in remaining) or 1
            running = 0
            for e in remaining:
                lane = min(len(fighter_slots) - 1,
                           int(running * len(fighter_slots) / total_remaining))
                zones[e["index"]] = fighter_slots[lane]
                running += e["gem_value"]
        elif remaining:
            for e in remaining:
                zones[e["index"]] = fighter_slots[0]

    return zones


def play():
    # Fix 2: choose priority list based on map type.
    # Evaluated once; result is consistent across all draft rounds since the map
    # doesn't change.  _is_burst_map() is cheap enough to call per round.
    priority  = PRIORITY_FIGHTER if _is_burst_map() else PRIORITY_ECONOMY

    chosen    = cambc.draft.current_draft(Team.ALLY)
    remaining = [pick for pick in priority if pick not in chosen]
    pick      = remaining[0]
    picks     = [*chosen, pick]
    team_size = cambc.draft.team_size()

    # Fix 1: pick the champion FIRST so it is never lost to a memory-write error.
    # The engine auto-picks a wrong champion when we call end_turn() without
    # picking; that auto-pick then appears in current_draft(ALLY) next round,
    # causing the intended champion to be skipped forever.
    cambc.draft.pick(pick)

    # Write the plan after picking; if this fails, we still got the right champion.
    try:
        zones      = plan_zones(picks, team_size)
        groups     = game_map.camp_groups()
        priorities = [_group_priority(g) for g in groups]
        roles           = [_ROLE_OF.get(p, ROLE_FIGHTER) for p in picks]
        bank_thresholds = [_BANK_GEMS[r] // 5 for r in roles]
        tavi_slot   = next((i for i, p in enumerate(picks) if p == Pick.TAVI),        None)
        willow_slot = next((i for i, p in enumerate(picks) if p == Pick.WILLOW),      None)
        vale_slot   = next((i for i, p in enumerate(picks) if p == Pick.VESPER_VALE), None)
        cambc.draft_memory.submit(encode_plan(
            picks, zones, priorities, roles, bank_thresholds,
            tavi_slot, willow_slot, vale_slot,
        ))
    except Exception:
        pass  # ponytail: plan write is best-effort; champions fall back to defaults
