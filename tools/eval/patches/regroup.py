import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Outnumbered: fall back onto the nearest ally (turning 1v2 into 2v2) rather than just away.
edit(D + "bot.py", [("""            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):
                nav.step_away(k, [enemy.position() for enemy in near], 6)
                return "retreat\"""", """            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):
                allies = [
                    ally.position()
                    for ally in cambc.vision.champions(Team.ALLY)
                    if ally != me
                    and _alive(ally)
                    and position.chebyshev_distance(ally.position()) > 1
                ]
                if allies:
                    nearest = min(allies, key=position.chebyshev_distance)
                    if nav.step_towards(k, nav.tiles_around(nearest, 1)):
                        return "regroup"
                nav.step_away(k, [enemy.position() for enemy in near], 6)
                return "retreat\"""")])
