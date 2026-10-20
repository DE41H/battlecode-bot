import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Cautious PvP: fight only with a clear edge, back off from even fights, and give up contested captures quickly.
edit(D + "bot.py", [
("""FIGHT_EDGE = 0.8
RETREAT_EDGE = 0.9""", """FIGHT_EDGE = 1.3
RETREAT_EDGE = 1.1
# Below this ratio we leave even with an empty bag and full health: dying costs 60 rounds of farming.
FLEE_EDGE = 0.7"""),
("""            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):""", """            if ratio < FLEE_EDGE or (ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            )):"""),
("""                and ratio >= 1.0
                and self.fight_enemies(intruders, aggressive=True)""", """                and ratio >= FIGHT_EDGE
                and self.fight_enemies(intruders, aggressive=True)"""),
("""CONTEST_TURNS = 4
CONTEST_BACKOFF = 30""", """CONTEST_TURNS = 2
CONTEST_BACKOFF = 40"""),
])
