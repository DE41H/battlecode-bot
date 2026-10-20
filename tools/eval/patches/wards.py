import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Wards: whenever the ward is off cooldown, move it to the tile in reach that shows the most we cannot see ourselves,
# bushes (ambush spots) counted triple and tiles on the enemy's side of us counted double.
edit(D + "bot.py", [
("""    def play_turn(self):
        mode = self.decide()
""", """    def play_turn(self):
        mode = self.decide()
        # Last: moving the ward drops the old ward's vision, and units seen through it must not vanish mid-turn.
        me = cambc.me()
        if me.is_alive() and not self.k.ally_spawn.is_set(me.position()):
            self.place_ward()
"""),
("""    # --------------------------------------------------------------- banking
""", """    # ---------------------------------------------------------------- vision

    def place_ward(self):
        me = cambc.me()
        if me.ward_cooldown() > 0 or cambc.fuel_remaining() < WARD_FUEL:
            return False
        k = self.k
        assert k is not None
        try:
            mine = me.visible_tiles()
            # Placement tiles can include walls, where a ward has no vision at all.
            tiles = me.ward_placement_tiles() & ~k.walls
        except cambc.Error:
            return False
        hidden = ~mine
        bush = k.bushes & hidden
        ahead = k.enemy_half & hidden

        def gain(tile):
            try:
                seen = cambc.Ward.visible_tiles_from(tile)
            except cambc.Error:
                return 0
            return (
                (seen & hidden).count()
                + 2 * (seen & bush).count()
                + (seen & ahead).count()
            )

        current = 0
        for ward in me.ward_positions():
            current = max(current, gain(ward))
        position = me.position()
        best, best_gain = None, current * WARD_SWITCH + WARD_MIN_GAIN
        for tile in tiles.positions():
            # Only the outer ring reaches past our own sight; inner tiles see little we do not.
            if position.chebyshev_distance(tile) < 2:
                continue
            value = gain(tile)
            if value > best_gain:
                best, best_gain = tile, value
        if best is None:
            return False
        try:
            return me.place_ward(best)
        except cambc.Error:
            return False

    # --------------------------------------------------------------- banking
"""),
("""DEBUG = False
""", """DEBUG = False
# Ward placement: minimum new tiles revealed, how much better a new spot must be, and fuel we keep in reserve.
WARD_MIN_GAIN = 6
WARD_SWITCH = 1.2
WARD_FUEL = 1_200_000
"""),
])
edit(D + "knowledge.py", [
("""        self.capture_time = cambc.constants.CAPTURE_TIME
""", """        self.capture_time = cambc.constants.CAPTURE_TIME
        self.bushes = game_map.bushes()
        self.walls = game_map.walls()
        # Tiles nearer the enemy spawn than ours, where threats come from.
        enemy = self.enemy_spawn.positions()
        ex, ey = sum(p.x for p in enemy) // len(enemy), sum(p.y for p in enemy) // len(enemy)
        sx, sy = self.spawn_center.x, self.spawn_center.y
        # Union over d of (within d of theirs, not within d of ours): one bitboard op per ring, not per tile.
        self.enemy_half = cambc.Bitboard()
        for d in range(max(game_map.width(), game_map.height())):
            theirs, ours = cambc.Bitboard(), cambc.Bitboard()
            theirs.draw_chebyshev(cambc.Vec2(ex, ey), d)
            ours.draw_chebyshev(cambc.Vec2(sx, sy), d)
            self.enemy_half |= theirs & ~ours
"""),
])
