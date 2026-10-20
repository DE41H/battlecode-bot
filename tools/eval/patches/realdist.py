import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Walking distances instead of Chebyshev ones: keep the spawn field we already build for reachability, add one field
# rooted at every tribute spot (both on the first turn, which has double fuel), and use them for target scoring
# (trip to spawn, walk to an altar) and for the nearest-altar checks that drive banking. Walls around altars
# (01hooks' walled centre) made straight-line distances badly wrong.
edit(D + "knowledge.py", [
("""        self.reach = cambc.Bitboard()
        cambc.DistanceField().compute(self.terrain, self.ally_spawn, self.reach)
""", """        self.reach = cambc.Bitboard()
        self.spawn_field = cambc.DistanceField()
        self.spawn_field.compute(self.terrain, self.ally_spawn, self.reach)
"""),
("""        for info in self.groups:
            info.altar_distance = self.nearest_altar_distance_xy(info.cx, info.cy)
            info.spawn_distance = max(
                abs(info.cx - self.spawn_center.x), abs(info.cy - self.spawn_center.y)
            )
""", """        # Walking distance to the nearest tribute spot, from every tile (one search from all spots at once).
        spots = cambc.Bitboard()
        for tiles in self.altar_spots:
            spots |= tiles
        self.altar_field = None
        if not spots.is_empty():
            self.altar_field = cambc.DistanceField()
            self.altar_field.compute(self.terrain, spots, cambc.Bitboard())
        for info in self.groups:
            info.altar_distance = self.nearest_altar_distance_xy(info.cx, info.cy)
            info.spawn_distance = max(
                abs(info.cx - self.spawn_center.x), abs(info.cy - self.spawn_center.y)
            )
            spawn_walk = min(self.spawn_field.get(p) for p in info.positions)
            if spawn_walk < 65535:
                info.spawn_distance = spawn_walk
            if self.altar_field is not None:
                altar_walk = min(self.altar_field.get(p) for p in info.positions)
                if altar_walk < 65535:
                    info.altar_distance = altar_walk + 1
"""),
("""    def nearest_altar_distance(self, position):
        return self.nearest_altar_distance_xy(position.x, position.y)
""", """    def nearest_altar_distance(self, position):
        if self.altar_field is not None:
            walk = self.altar_field.get(position)
            if walk < 65535:
                return walk + 1
        return self.nearest_altar_distance_xy(position.x, position.y)
"""),
])
