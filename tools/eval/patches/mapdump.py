import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: champion 0 prints an ASCII map (# wall, o hole, " bush, A altar, S/E spawns, group index as base-36 on
# camp tiles), every group's camps, and the camp designs, on its first turn.
edit(D + "bot.py", [
("""    def setup(self):
        me = cambc.me()
        self.k = Knowledge()""",
"""    def setup(self):
        me = cambc.me()
        self.k = Knowledge()
        if int(me) == 0:
            from cambc import game_map
            w, h = game_map.width(), game_map.height()
            walls, holes, bushes, altars = game_map.walls(), game_map.holes(), game_map.bushes(), game_map.altars()
            ally, enemy = game_map.spawn_region(Team.ALLY), game_map.spawn_region(Team.ENEMY)
            owner = {}
            for info in self.k.groups:
                for p in info.positions:
                    owner[(p.x, p.y)] = "0123456789abcdefghijklmnopqrstuvwxyzABCDFGHIJKLMNPQRTUVWXYZ"[info.index % 58]
            grid = [["."] * w for _ in range(h)]
            for board, ch in ((bushes, '"'), (enemy, "E"), (ally, "S"), (altars, "A"), (holes, "o"), (walls, "#")):
                for p in board.positions():
                    grid[p.y][p.x] = ch
            for (x, y), c in owner.items():
                grid[y][x] = c
            for row in grid:
                print("MAP", "".join(row))
            for info in self.k.groups:
                kinds = [int(c.kind()) for c in info.group.camps()]
                print("GROUP", info.index, info.cx, info.cy, "gems", info.gems, "gold", info.gold, "resp", info.respawn, "hp", info.max_health, "str", info.strength, "kinds", kinds)
            for kind in range(6):
                s = cambc.CampType(kind) if hasattr(cambc, "CampType") else kind
                try:
                    import _cambc
                    st = _cambc.camp_design(kind)
                    print("CAMPDESIGN", kind, st.base_health, st.base_strength, st.base_attack_range, st.vision_radius, st.health_growth, st.strength_growth)
                except Exception as e:
                    print("CAMPDESIGN", kind, repr(e))
            print("SPAWN", self.k.spawn_center.x, self.k.spawn_center.y, "ALTARS", self.k.altar_xy, flush=True)"""),
])
