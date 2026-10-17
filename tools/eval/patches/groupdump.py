import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: dump the group table once and every re-plan's top candidates.
edit(D + "bot.py", [
("""        scored.sort(reverse=True)
        field = cambc.DistanceField()""",
"""        scored.sort(reverse=True)
        print("PLAN", now, int(me), int(me.champion_name()), px, py, [(round(s, 3), i, round(t)) for s, i, t in scored[:6]])
        field = cambc.DistanceField()"""),
("""    def setup(self):
        me = cambc.me()
        self.k = Knowledge()""",
"""    def setup(self):
        me = cambc.me()
        self.k = Knowledge()
        if int(me) == 0:
            for info in self.k.groups:
                print("GROUP", info.index, info.cx, info.cy, info.gems, info.gold, info.respawn, info.max_health, info.strength, info.radius, info.altar_distance, info.spawn_distance, self.k.scoring[info.index][-1])
            print("SPAWN", self.k.spawn_center.x, self.k.spawn_center.y, "ALTARS", self.k.altar_xy)"""),
])
