import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Allies on the region split the reward; keeping both spreads gold so everyone gets items.
edit(D + "bot.py", [("""        if info.tiles.is_set(position):
            # Two of us on the region only splits the reward; the higher id leaves.
            if any(int(ally) < int(me) for ally in allies_on):
                k.captured(info.index)
                self.target = None
            return
        if allies_on:
            k.captured(info.index)
            self.target = None
            return
        nav.step_towards(k, info.tiles)""", """        if info.tiles.is_set(position):
            return
        nav.step_towards(k, info.tiles)""")])
