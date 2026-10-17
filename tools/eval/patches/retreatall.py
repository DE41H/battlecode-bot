import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Heavily outnumbered: leave even with an empty bag and full health, before the group closes in.
edit(D + "bot.py", [("""            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):""", """            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0
                or me.health() < me.max_health() * 0.6
                or ratio < 0.5
            ):""")])
