"""Static map facts and each champion's memory of camp respawns."""

import cambc
import memory
from cambc import game_map

Team = cambc.Team


class GroupInfo:
    """Fixed facts about one camp group, read once from the map."""

    def __init__(self, group):
        self.group = group
        self.index = int(group)
        self.gems = group.gem_value()
        self.gold = group.gold_value()
        self.respawn = group.max_respawn_timer()
        self.tiles = group.spawn_tiles()
        self.positions = self.tiles.positions()
        camps = group.camps()
        self.max_health = sum(camp.base_stats().base_health for camp in camps)
        # Gem and gold clusters have no strength, so a pure cluster group is harmless.
        self.strength = sum(camp.base_stats().base_strength for camp in camps)
        xs = [p.x for p in self.positions]
        ys = [p.y for p in self.positions]
        # Plain ints: Python arithmetic is far cheaper in fuel than SDK calls in hot loops.
        self.cx, self.cy = sum(xs) // len(xs), sum(ys) // len(ys)
        self.center = cambc.Vec2(self.cx, self.cy)
        self.radius = max(
            max(abs(p.x - self.cx), abs(p.y - self.cy)) for p in self.positions
        )
        self.anchor = min(
            self.positions, key=lambda p: max(abs(p.x - self.cx), abs(p.y - self.cy))
        )
        # Filled in by Knowledge once the altars and spawn are known.
        self.altar_distance = 0
        self.spawn_distance = 0


class Knowledge:
    """Map cache plus a per-champion table of when each camp group is next worth visiting."""

    def __init__(self):
        self.groups = [GroupInfo(group) for group in game_map.camp_groups()]
        self.ally_spawn = game_map.spawn_region(Team.ALLY)
        self.enemy_spawn = game_map.spawn_region(Team.ENEMY)
        self.terrain = (
            game_map.walls() | game_map.holes() | game_map.altars() | self.enemy_spawn
        )
        # Tiles we can walk to from spawn; camps count as floor since they die. Holes cut off whole islands.
        self.reach = cambc.Bitboard()
        cambc.DistanceField().compute(self.terrain, self.ally_spawn, self.reach)
        for info in self.groups:
            info.reachable = not (info.tiles & self.reach).is_empty()
        # Tribute spots: walkable tiles next to each altar. An altar whose spots are all camp tiles stays shut
        # until that camp group dies (01boss-battle's only altar sits behind its monoliths).
        self.all_altars = game_map.altars().positions()
        self.altars, self.altar_spots, self.altar_gates = [], [], []
        for altar in self.all_altars:
            ring = cambc.Bitboard()
            ring.draw_chebyshev(altar, cambc.constants.SUBMIT_GEMS_RANGE)
            spots = ring & self.reach
            if spots.is_empty():
                continue
            gates = []
            open_spots = spots.copy()
            for info in self.groups:
                if not (spots & info.tiles).is_empty():
                    gates.append(info.index)
                    open_spots = open_spots & ~info.tiles
            self.altars.append(altar)
            self.altar_spots.append(spots)
            self.altar_gates.append([] if not open_spots.is_empty() else gates)
        if not self.altars:
            self.altars = self.all_altars
            self.altar_spots = [cambc.Bitboard() for _ in self.altars]
            self.altar_gates = [[] for _ in self.altars]
        self.gates = {index for gates in self.altar_gates for index in gates}
        # Enemy altar locks as last seen, per altar index.
        self.locked = [False] * len(self.altars)
        # Spawn tile -> group index; camp.camp_group() rebuilds the whole group and costs ~20k fuel a call.
        self.group_at = {
            (p.x, p.y): info.index for info in self.groups for p in info.positions
        }
        # Every group's spawn tiles: standing on one holds that whole group's respawn.
        self.spawn_tiles = cambc.Bitboard()
        for info in self.groups:
            self.spawn_tiles |= info.tiles
        # Tiles of camps that hit back: splash or a dash landing on one wakes its whole group.
        self.armed = cambc.Bitboard()
        for info in self.groups:
            if info.strength > 0:
                self.armed |= info.tiles
        self._collateral = {}
        self._armed_within = {}
        self.altar_xy = [(a.x, a.y) for a in self.altars]
        spawn = self.ally_spawn.positions()
        self.spawn_center = cambc.Vec2(
            sum(p.x for p in spawn) // len(spawn), sum(p.y for p in spawn) // len(spawn)
        )
        for info in self.groups:
            info.altar_distance = self.nearest_altar_distance_xy(info.cx, info.cy)
            info.spawn_distance = max(
                abs(info.cx - self.spawn_center.x), abs(info.cy - self.spawn_center.y)
            )
        self.capture_time = cambc.constants.CAPTURE_TIME
        self.bushes = game_map.bushes()
        self.walls = game_map.walls()
        # Tiles nearer the enemy spawn than ours, where threats come from.
        enemy = self.enemy_spawn.positions()
        ex = sum(p.x for p in enemy) // len(enemy)
        ey = sum(p.y for p in enemy) // len(enemy)
        sx, sy = self.spawn_center.x, self.spawn_center.y
        # Union over d of (within d of theirs, not within d of ours): one bitboard op per ring, not per tile.
        self.enemy_half = cambc.Bitboard()
        for d in range(max(game_map.width(), game_map.height())):
            theirs, ours = cambc.Bitboard(), cambc.Bitboard()
            theirs.draw_chebyshev(cambc.Vec2(ex, ey), d)
            ours.draw_chebyshev(cambc.Vec2(sx, sy), d)
            self.enemy_half |= theirs & ~ours
        self.scoring = self.scoring_table(memory.Plan().zones)
        # Round from which a group is expected to be alive again; unknown groups are assumed alive.
        self.available = [0] * len(self.groups)
        # Groups whose reward is waiting to be captured (all camps dead, not yet claimed).
        self.reward_ready = [False] * len(self.groups)
        # Health left in each group; camps do not heal while asleep, so damage is banked progress.
        self.remaining = [float(info.max_health) for info in self.groups]
        # Round until which we stay away from a group, e.g. after losing a capture contest.
        self.avoid = [0] * len(self.groups)
        # This turn's visible camps as (camp, group index, health), filled by observe.
        self.seen = []

    def scoring_table(self, zones):
        """Static per-group terms for target scoring, as flat tuples for a cheap inner loop."""
        recall = cambc.constants.RECALL_TIME
        table = []
        for info in self.groups:
            if not info.reachable:
                continue
            zone = zones[info.index] if info.index < len(zones) else memory.SHARED
            table.append(
                (
                    info.index,
                    info.cx,
                    info.cy,
                    info.gems + 0.35 * info.gold,
                    info.gems + 0.1 * info.gold if info.gems > 0 else 0.0,
                    2.5 * info.spawn_distance + recall,
                    0.4 * info.altar_distance + 1,
                    info.strength,
                    -1 if zone == memory.SHARED else zone,
                )
            )
        return table

    def observe(self):
        """Refresh respawn timers for every camp group currently in vision."""
        now = cambc.round_number()
        # One pass over the visible camps per turn; SDK calls dominate our fuel, so everything else reuses it.
        self.seen = []
        health = {}
        group_at = self.group_at
        for camp in cambc.vision.camps():
            spawn = camp.spawn_position()
            index = group_at.get((spawn.x, spawn.y))
            if index is None:
                index = int(camp.camp_group())
            hp = camp.health()
            self.seen.append((camp, index, hp))
            if hp > 0:
                health[index] = health.get(index, 0.0) + hp
        me = cambc.me().position()
        # Our vision plus a ward placed nearby never reaches beyond about 8 tiles.
        nearby = [
            info
            for info in self.groups
            if max(abs(info.cx - me.x), abs(info.cy - me.y)) - info.radius <= 8
        ]
        if not nearby:
            return
        visible = cambc.vision.visible_tiles()
        for info in nearby:
            if (info.tiles & visible).is_empty():
                continue
            try:
                state = info.group.state()
            except cambc.Error:
                continue
            if isinstance(state, game_map.CampGroupRespawning):
                self.available[info.index] = now + state.timer
                self.reward_ready[info.index] = False
                self.remaining[info.index] = info.max_health
            elif isinstance(state, game_map.CampGroupRewardAvailable):
                self.available[info.index] = now
                self.reward_ready[info.index] = True
                self.remaining[info.index] = 0.0
            else:
                self.available[info.index] = now
                self.reward_ready[info.index] = False
                if info.index in health:
                    self.remaining[info.index] = health[info.index]

    def captured(self, index):
        """Record that we just took a group's reward."""
        info = self.groups[index]
        self.available[index] = cambc.round_number() + info.respawn
        self.reward_ready[index] = False
        self.remaining[index] = info.max_health

    def collateral(self, index):
        """Armed camp tiles outside group index, which our splash must not touch while we farm it."""
        tiles = self._collateral.get(index)
        if tiles is None:
            tiles = self.armed & ~self.groups[index].tiles
            self._collateral[index] = tiles
        return tiles

    def armed_within(self, radius):
        """Tiles within radius of an armed camp tile."""
        tiles = self._armed_within.get(radius)
        if tiles is None:
            tiles = self.armed.copy()
            for position in self.armed.positions():
                tiles.draw_chebyshev(position, radius)
            self._armed_within[radius] = tiles
        return tiles

    def gate_alive(self, index):
        return self.available[index] <= cambc.round_number() and not self.reward_ready[index]

    def open_altars(self):
        """Indices of altars with a tribute spot we can stand on now (as far as we know)."""
        return [
            i
            for i, gates in enumerate(self.altar_gates)
            if not any(self.gate_alive(index) for index in gates)
        ]

    def nearest_altar_distance(self, position):
        return self.nearest_altar_distance_xy(position.x, position.y)

    def nearest_altar_distance_xy(self, x, y):
        if not self.altar_xy:
            return 999
        return min(max(abs(x - ax), abs(y - ay)) for ax, ay in self.altar_xy)
