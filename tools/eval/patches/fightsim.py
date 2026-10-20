import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Fight lookahead: replace the Lanchester product (sum health x sum damage) with a short simulation of the local
# fight. Every visible champion within SIM_RADIUS gets a damage-per-round estimate from its kit (attack resets,
# damaging spells by focus, Varg's shield and splash), starts hitting once it has walked into reach, and both sides
# focus the opposing unit with the lowest health. The outcome maps back onto the old ratio scale via the square law
# (a winner keeping fraction f of its health is R = 1 / (1 - f^2); a loss mirrors it), so FIGHT_EDGE, RETREAT_EDGE
# and PRESS_EDGE keep their meaning.
edit(D + "combat.py", [
("""def local_advantage(enemies, radius=6):
    \"\"\"Our power over theirs within radius of us, and the enemies counted; ratio is None with no enemies.\"\"\"
    me = cambc.me()
    position = me.position()
    near = [
        enemy
        for enemy in enemies
        if position.chebyshev_distance(enemy.position()) <= radius
    ]
    if not near:
        return None, near
    allies = [me] + [
        ally
        for ally in cambc.vision.champions(Team.ALLY)
        if ally != me
        and _alive(ally)
        and position.chebyshev_distance(ally.position()) <= radius
    ]
    return fighting_power(allies) / max(1.0, fighting_power(near)), near
""", """# Per champion type: (attack resets, total damaging-spell focus multiplier over both slots).
_KIT = {
    0: (1, 1.0),  # Ryth: area stun 1.0
    1: (1, 0.0),  # Vesper Vale
    2: (1, 0.0),  # Vendetta
    3: (0, 2.0),  # Cassi: 2.0 nuke (+ stun)
    4: (1, 0.0),  # Issac
    5: (0, 3.4),  # Stellar: 2.0 nuke + 1.4 area
    6: (0, 2.5),  # Prism: 1.5 (+ stun) + 1.0 area
    7: (1, 2.0),  # Marcella: 2.0 nuke
    8: (1, 0.0),  # Willow
    9: (0, 1.25),  # Ren: 1.25 (+ stun)
    10: (1, 0.0),  # Varg: splash and shield handled below
    11: (1, 2.2),  # Tavi: 2.2 (+ stun)
    12: (1, 0.0),  # Heart of Ruin
}
SIM_RADIUS = 8
SIM_ROUNDS = 30
_VARG = int(cambc.ChampionType.VARG)


def _unit(champion):
    \"\"\"[health, damage per round, reach, x, y] for one champion.\"\"\"
    kind = int(champion.champion_name())
    resets, spells = _KIT.get(kind, (0, 0.0))
    strength, focus = champion.strength(), champion.focus()
    damage = strength * (1 + resets / 8) + focus * spells / 8
    health = max(0.0, champion.health())
    if kind == _VARG:
        health += 2.5 * focus
        damage *= 1.2
    reach = max(champion.attack_range(), 4 if spells > 0 else 1)
    position = champion.position()
    return [health, damage, reach, position.x, position.y]


def _hit(units, damage):
    \"\"\"Apply damage to the weakest living unit first, spilling over to the next.\"\"\"
    while damage > 0:
        alive = [unit for unit in units if unit[0] > 0]
        if not alive:
            return
        target = min(alive, key=lambda unit: unit[0])
        dealt = min(damage, target[0])
        target[0] -= dealt
        damage -= dealt


def simulate(ours, theirs):
    \"\"\"Simulated outcome on the Lanchester ratio scale (>1 we win, <1 they win).\"\"\"
    for side, other in ((ours, theirs), (theirs, ours)):
        for unit in side:
            gap = min(max(abs(unit[3] - o[3]), abs(unit[4] - o[4])) for o in other)
            unit.append(max(0, gap - unit[2]))
    start_ours = sum(unit[0] for unit in ours) or 1.0
    start_theirs = sum(unit[0] for unit in theirs) or 1.0
    for turn in range(SIM_ROUNDS):
        ours_damage = sum(u[1] for u in ours if u[0] > 0 and u[5] <= turn)
        theirs_damage = sum(u[1] for u in theirs if u[0] > 0 and u[5] <= turn)
        _hit(theirs, ours_damage)
        _hit(ours, theirs_damage)
        if not any(u[0] > 0 for u in ours) or not any(u[0] > 0 for u in theirs):
            break
    left_ours = sum(max(0.0, u[0]) for u in ours) / start_ours
    left_theirs = sum(max(0.0, u[0]) for u in theirs) / start_theirs
    if left_theirs <= 0 < left_ours:
        return min(10.0, 1 / max(0.1, 1 - left_ours * left_ours))
    if left_ours <= 0 < left_theirs:
        return 1 - left_theirs * left_theirs
    # Undecided (or mutual wipe): compare the share of health each side lost.
    return ((1 - left_theirs) + 0.05) / ((1 - left_ours) + 0.05)


def local_advantage(enemies, radius=6):
    \"\"\"Simulated odds of the local fight, and the enemies within radius; ratio is None with no enemies.\"\"\"
    me = cambc.me()
    position = me.position()
    near = [
        enemy
        for enemy in enemies
        if position.chebyshev_distance(enemy.position()) <= radius
    ]
    if not near:
        return None, near
    reach = max(radius, SIM_RADIUS)
    theirs = [
        _unit(enemy)
        for enemy in enemies
        if position.chebyshev_distance(enemy.position()) <= reach
    ]
    ours = [_unit(me)] + [
        _unit(ally)
        for ally in cambc.vision.champions(Team.ALLY)
        if ally != me
        and _alive(ally)
        and position.chebyshev_distance(ally.position()) <= reach
    ]
    return simulate(ours, theirs), near
"""),
])
