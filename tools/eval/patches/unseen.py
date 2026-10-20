import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Camps see through bushes and we do not: on 01corridors camps behind a bush row hit champions walking past, and
# a low champion kept restarting a recall that every hit cancelled (12 of 18 camp deaths in a traced game).
# When hit, armed camp tiles within 4 count as threats even unseen, and we never start a recall that turn.
edit(D + "bot.py", [
("""            threats += [
                c.position()
                for c in hostile_camps
                if position.chebyshev_distance(c.position()) <= 4
            ]""", """            threats += [
                c.position()
                for c in hostile_camps
                if position.chebyshev_distance(c.position()) <= 4
            ]
            if damage > 0:
                # A camp behind a bush or wall can hit us unseen; any hit would cancel a recall anyway.
                threats += (nav.tiles_around(position, 4) & k.armed).positions()
                if not threats:
                    nav.step_towards(k, k.ally_spawn)
                    return "low-hit\""""),
])
