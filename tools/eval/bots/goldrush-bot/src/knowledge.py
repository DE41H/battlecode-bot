"""Static map facts and per-champion camp respawn memory.

Extends main-bot's Knowledge with group_priority multipliers sourced from the
draft plan, so the scoring loop rewards high-value camps (Elk, Monolith) and
de-weights camps outside a champion's role (e.g. pure gold clusters for non-Vale).
"""

import cambc
import memory
from cambc import game_map

Team, CampType = cambc.Team, cambc.CampType

MONOLITH = CampType.MONOLITH

# Score multipliers per priority tier.
_PRIO_MULT = {
    memory.PRIO_HIGH:   1.25,
    memory.PRIO_NORMAL: 1.00,
    memory.PRIO_LOW:    0.60,
}


class GroupInfo:
    """Fixed facts about one camp group, read once from the map."""

    def __init__(self, group):
        self.group        = group
        self.index        = int(group)
        self.gems         = group.gem_value()
        self.gold         = group.gold_value()
        self.respawn      = group.max_respawn_timer()
        self.tiles        = group.spawn_tiles()
        self.positions    = self.tiles.positions()
        camps             = group.camps()
        self.max_health   = sum(camp.base_stats().base_health for camp in camps)
        self.strength     = sum(camp.base_stats().base_strength for camp in camps)
        self.has_monolith = any(camp.kind() == MONOLITH for camp in camps)
        xs = [p.x for p in self.positions]
        ys = [p.y for p in self.positions]
        self.cx, self.cy  = sum(xs) // len(xs), sum(ys) // len(ys)
        self.center       = cambc.Vec2(self.cx, self.cy)
        self.radius       = max(max(abs(p.x - self.cx), abs(p.y - self.cy)) for p in self.positions)
        self.anchor       = min(self.positions, key=lambda p: max(abs(p.x - self.cx), abs(p.y - self.cy)))
        self.altar_distance = 0
        self.spawn_distance = 0


class Knowledge:
    """Map cache plus per-champion table of when each group is next worth visiting."""

    def __init__(self):
        self.groups      = [GroupInfo(g) for g in game_map.camp_groups()]
        self.altars      = game_map.altars().positions()
        self.altar_xy    = [(a.x, a.y) for a in self.altars]
        self.ally_spawn  = game_map.spawn_region(Team.ALLY)
        self.enemy_spawn = game_map.spawn_region(Team.ENEMY)
        spawn            = self.ally_spawn.positions()
        self.spawn_center = cambc.Vec2(
            sum(p.x for p in spawn) // len(spawn),
            sum(p.y for p in spawn) // len(spawn),
        )
        for info in self.groups:
            info.altar_distance = self.nearest_altar_distance_xy(info.cx, info.cy)
            info.spawn_distance = max(
                abs(info.cx - self.spawn_center.x), abs(info.cy - self.spawn_center.y)
            )
        self.capture_time = cambc.constants.CAPTURE_TIME
        plan              = memory.Plan()
        self.scoring      = self.scoring_table(plan.zones, plan.priorities)
        self.terrain      = (
            game_map.walls() | game_map.holes() | game_map.altars() | self.enemy_spawn
        )
        self.available    = [0]   * len(self.groups)
        self.reward_ready = [False] * len(self.groups)
        self.remaining    = [float(info.max_health) for info in self.groups]
        self.avoid        = [0]   * len(self.groups)

    def scoring_table(self, zones, priorities):
        """Static per-group terms for target scoring, as flat tuples for a cheap inner loop.

        Adds a priority_mult column sourced from the draft plan so champions
        automatically prefer Elk > Wolf > Gold-cluster without zone-affinity hacks.
        """
        recall = cambc.constants.RECALL_TIME
        table  = []
        for info in self.groups:
            if info.has_monolith:
                continue  # monolith handled separately via monolith_down signal
            zone     = zones[info.index]      if info.index < len(zones)      else memory.SHARED
            prio     = priorities[info.index] if info.index < len(priorities) else memory.PRIO_NORMAL
            prio_mult = _PRIO_MULT.get(prio, 1.0)
            table.append((
                info.index,
                info.cx,
                info.cy,
                info.gems + 0.35 * info.gold,             # early value
                # Fix 1: gold camps get a small late value so Vale stays active post-700
                info.gems + 0.1 * info.gold if info.gems > 0 else 0.05 * info.gold,
                2.5 * info.spawn_distance + recall,       # trip_cost
                0.4 * info.altar_distance + 1,            # fixed banking overhead
                info.strength,                            # camp danger
                -1 if zone == memory.SHARED else zone,   # zone owner slot
                prio_mult,                                # priority multiplier
                # Fix 2: raw gold/gems so Vale's boost uses correct fraction
                info.gold,
                info.gems,
            ))
        return table

    def observe(self):
        """Refresh respawn timers for every camp group currently in vision."""
        now    = cambc.round_number()
        me     = cambc.me().position()
        nearby = [
            info for info in self.groups
            if max(abs(info.cx - me.x), abs(info.cy - me.y)) - info.radius <= 8
        ]
        if not nearby:
            return
        visible = cambc.vision.visible_tiles()
        health  = {}
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
                self.available[info.index]    = now + state.timer
                self.reward_ready[info.index] = False
                self.remaining[info.index]    = info.max_health
            elif isinstance(state, game_map.CampGroupRewardAvailable):
                self.available[info.index]    = now
                self.reward_ready[info.index] = True
                self.remaining[info.index]    = 0.0
            else:
                self.available[info.index]    = now
                self.reward_ready[info.index] = False
                if info.index in health:
                    self.remaining[info.index] = health[info.index]
                # Fix 6: monolith is alive — clear the signal so fighters don't
                # chase it forever after a different champion already captured it.
                if info.has_monolith:
                    memory.write_monolith_down(False)

            # Broadcast monolith-down signal if we see the Monolith is dead/reward-ready.
            if info.has_monolith and (
                isinstance(state, game_map.CampGroupRewardAvailable)
                or (isinstance(state, game_map.CampGroupRespawning) and state.timer <= 5)
            ):
                memory.write_monolith_down(True)

    def captured(self, index):
        """Record that we just took a group's reward."""
        info                      = self.groups[index]
        self.available[index]     = cambc.round_number() + info.respawn
        self.reward_ready[index]  = False
        self.remaining[index]     = info.max_health
        if info.has_monolith:
            memory.write_monolith_down(False)

    def nearest_altar_distance(self, position):
        return self.nearest_altar_distance_xy(position.x, position.y)

    def nearest_altar_distance_xy(self, x, y):
        if not self.altar_xy:
            return 999
        return min(max(abs(x - ax), abs(y - ay)) for ax, ay in self.altar_xy)

    def monolith_groups(self):
        """Return GroupInfo objects that contain a Monolith."""
        return [info for info in self.groups if info.has_monolith]
