import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Remember enemy altar locks: has_altar_lock() is False whenever the altar is out of view, so judging locks only by
# what we see this turn made champions oscillate between a locked altar and a far one. A lock counts until we see
# that altar again without it.
edit(D + "bot.py", [("""        open_altars = k.open_altars()
        altars = []
        for i in open_altars:
            altar = k.altars[i]
            try:
                if (
                    cambc.vision.has_altar_lock(altar)
                    and cambc.vision.altar_lock_at(altar).is_enemy()
                ):
                    continue
            except cambc.Error:
                pass
            altars.append(i)
        return altars or open_altars""", """        open_altars = k.open_altars()
        visible = cambc.vision.visible_tiles()
        altars = []
        for i in open_altars:
            altar = k.altars[i]
            if visible.is_set(altar):
                try:
                    k.locked[i] = (
                        cambc.vision.has_altar_lock(altar)
                        and cambc.vision.altar_lock_at(altar).is_enemy()
                    )
                except cambc.Error:
                    k.locked[i] = False
            if not k.locked[i]:
                altars.append(i)
        return altars or open_altars""")])
edit(D + "knowledge.py", [("""        self.gates = {index for gates in self.altar_gates for index in gates}
""", """        self.gates = {index for gates in self.altar_gates for index in gates}
        # Enemy altar locks as last seen, per altar index.
        self.locked = [False] * len(self.altars)
""")])
