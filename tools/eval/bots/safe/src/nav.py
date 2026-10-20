"""Pathing: one bounded search per call toward a set of goal tiles."""

import cambc

Team = cambc.Team


def tiles_around(position, radius):
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def blocked_tiles(knowledge):
    # Terrain plus everything visibly standing on a tile, except ourselves.
    blocked = (
        knowledge.terrain
        | cambc.vision.champion_tiles()
        | cambc.vision.camp_tiles()
        | cambc.vision.teleport_tiles()
    )
    blocked.set(cambc.me().position(), False)
    return blocked


# Turns in a row we wanted to move and could not; drives deadlock breaking.
_stuck = {"position": None, "turns": 0}


def _try_move(me, step):
    try:
        return me.move_absolute(step)
    except cambc.Error:
        return False


def step_towards(knowledge, goals, avoid=None):
    """Walk one tile toward the nearest goal; returns True if we moved."""
    me = cambc.me()
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False
    if _stuck["position"] != origin:
        _stuck["position"], _stuck["turns"] = origin, 0
    stuck = _stuck["turns"]

    blocked = blocked_tiles(knowledge)
    # Plan through allies (they move on their own turn) unless that has already left us stuck.
    planning = (
        blocked if stuck >= 2 else blocked & ~cambc.vision.champion_tiles(Team.ALLY)
    )
    if avoid is not None:
        blocked |= avoid
        planning |= avoid
    goals = goals & ~planning
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)
    moved = False
    if not goals.is_empty():
        # Expand from the goals until our tile is reached, then take any strictly downhill step.
        field = cambc.DistanceField()
        field.compute_to(
            planning & ~goals, goals, tiles_around(origin, 0), cambc.Bitboard()
        )
        here = field.get(origin)
        if here < 65535:
            for step in sorted(reachable.positions(), key=field.get):
                if field.get(step) >= here:
                    break
                if _try_move(me, step):
                    moved = True
                    break
    if not moved and stuck >= 4:
        # Still wedged: step aside so whoever is in the way can pass.
        options = [step for step in reachable.positions() if step != origin]
        if options:
            moved = _try_move(
                me, options[(cambc.round_number() + int(me)) % len(options)]
            )
    _stuck["turns"] = 0 if moved else stuck + 1
    return moved


def step_away(knowledge, threats, radius):
    """Walk to a tile that maximises distance from the threat positions."""
    me = cambc.me()
    if not me.can_move() or not threats:
        return False
    origin = me.position()
    blocked = blocked_tiles(knowledge)
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)

    def safety(tile):
        return min(tile.chebyshev_distance(threat) for threat in threats)

    best = max([origin, *reachable.positions()], key=safety)
    if best == origin or safety(best) <= safety(origin):
        # Nothing strictly safer nearby: head home instead.
        return step_towards(knowledge, knowledge.ally_spawn)
    return _try_move(me, best)


def dash_towards(knowledge, ability, goals):
    """Spend a dash on travel if it brings us strictly closer to the goals, never landing a hit on a camp."""
    me = cambc.me()
    origin = me.position()
    if goals.is_set(origin):
        return False
    blocked = blocked_tiles(knowledge)
    field = cambc.DistanceField()
    field.compute_to(blocked & ~goals, goals, tiles_around(origin, 0), cambc.Bitboard())
    here = field.get(origin)
    if here >= 65535 or here <= 2:
        return False
    landing = tiles_around(origin, 2) & ~blocked
    info = ability.info()
    if info is not None and (info.modifier > 0 or info.duration > 0):
        # Landing damage wakes any camp group it touches; keep dashes clear of armed camps.
        landing &= ~knowledge.armed_within(int(info.radius))
    best = min(landing.positions(), key=field.get, default=None)
    if best is None or field.get(best) > here - 2:
        return False
    try:
        return ability.use(best)
    except cambc.Error:
        return False
