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
        self.altars = game_map.altars().positions()
        self.altar_xy = [(a.x, a.y) for a in self.altars]
        self.ally_spawn = game_map.spawn_region(Team.ALLY)
        self.enemy_spawn = game_map.spawn_region(Team.ENEMY)
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
        self.scoring = self.scoring_table(memory.Plan().zones)
        self.terrain = (
            game_map.walls() | game_map.holes() | game_map.altars() | self.enemy_spawn
        )
        # Round from which a group is expected to be alive again; unknown groups are assumed alive.
        self.available = [0] * len(self.groups)
        # Groups whose reward is waiting to be captured (all camps dead, not yet claimed).
        self.reward_ready = [False] * len(self.groups)
        # Health left in each group; camps do not heal while asleep, so damage is banked progress.
        self.remaining = [float(info.max_health) for info in self.groups]
        # Round until which we stay away from a group, e.g. after losing a capture contest.
        self.avoid = [0] * len(self.groups)

    def scoring_table(self, zones):
        """Static per-group terms for target scoring, as flat tuples for a cheap inner loop."""
        recall = cambc.constants.RECALL_TIME
        table = []
        for info in self.groups:
            zone = zones[info.index] if info.index < len(zones) else memory.SHARED
            table.append(
                (
                    info.index,
                    info.cx,
                    info.cy,
                    info.gems + 0.35 * info.gold,
                    info.gems + 0.1 * info.gold if info.gems > 0 else 0.0,
                    1.25 * info.spawn_distance + recall,
                    0.4 * info.altar_distance + 1,
                    info.strength,
                    -1 if zone == memory.SHARED else zone,
                )
            )
        return table

    def observe(self):
        """Refresh respawn timers for every camp group currently in vision."""
        now = cambc.round_number()
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
        health = {}
        for camp in cambc.vision.camps():
            index = int(camp.camp_group())
            health[index] = health.get(index, 0.0) + max(0.0, camp.health())
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

    def nearest_altar_distance(self, position):
        return self.nearest_altar_distance_xy(position.x, position.y)

    def nearest_altar_distance_xy(self, x, y):
        if not self.altar_xy:
            return 999
        return min(max(abs(x - ax), abs(y - ay)) for ax, ay in self.altar_xy)
