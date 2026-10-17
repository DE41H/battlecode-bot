import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Two of us already on an ordinary group: a third only waits beside them, so look elsewhere.
edit(D + "bot.py", [("""            team = 1 + others_on.get(index, 0)
            kill = remaining[index] / (dps * team)""", """            team = 1 + others_on.get(index, 0)
            if team > 2 and strength < 300:
                continue
            kill = remaining[index] / (dps * team)""")])
