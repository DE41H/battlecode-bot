import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [
("""        # Low health: recall if nothing can interrupt it, otherwise back off first.
        if not at_spawn and me.health() < me.max_health() * LOW_HEALTH:""",
"""        # Low health: recall if nothing can interrupt it, otherwise back off first.
        # Cassi and Issac die together, so either one falling costs both bodies and both bags.
        linked = me.champion_name() in (Kind.CASSI, Kind.ISSAC)
        low = LINKED_LOW_HEALTH if linked else LOW_HEALTH
        if not at_spawn and me.health() < me.max_health() * low:"""),
("LOW_HEALTH = 0.35\n", "LOW_HEALTH = 0.35\nLINKED_LOW_HEALTH = 0.5\n"),
])
