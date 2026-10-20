import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Squad play on contested camps (no more than 25% farther from the enemy spawn than from ours):
# allies pile onto the same contested target instead of splitting its value, and nobody walks in until
# min(3, living slots) of us stand together at a staging point 9 tiles back toward our spawn (25-round cap).
edit(D + "knowledge.py", [("""        self.capture_time = cambc.constants.CAPTURE_TIME
""", """        self.capture_time = cambc.constants.CAPTURE_TIME
        enemy = self.enemy_spawn.positions()
        ecx = sum(p.x for p in enemy) // len(enemy)
        ecy = sum(p.y for p in enemy) // len(enemy)
        self.contested = set()
        self.staging = {}
        for info in self.groups:
            ours = info.spawn_distance
            theirs = max(abs(info.cx - ecx), abs(info.cy - ecy))
            if theirs <= ours * CONTESTED:
                self.contested.add(info.index)
                # Step back from the group toward our spawn, SQUAD_BACK tiles in Chebyshev terms.
                dx = self.spawn_center.x - info.cx
                dy = self.spawn_center.y - info.cy
                span = max(abs(dx), abs(dy), 1)
                back = min(SQUAD_BACK, span)
                self.staging[info.index] = cambc.Vec2(
                    info.cx + dx * back // span, info.cy + dy * back // span
                )
"""), ("""Team = cambc.Team
""", """Team = cambc.Team
# A group is contested when the enemy spawn is at most this much farther from it than ours.
CONTESTED = 1.25
# Staging distance from a contested group, toward our spawn.
SQUAD_BACK = 9
""")])
edit(D + "bot.py", [
("""            team = 1 + others_on.get(index, 0)
            kill = remaining[index] / (dps * team)""", """            team = 1 + others_on.get(index, 0)
            kill = remaining[index] / (dps * team)
            # Contested camps are taken together: allies there speed the clear without splitting its worth.
            split = 1 if index in contested else team"""),
("""            score = (late_value if late else early) / (busy * team + capture_time)""", """            score = (late_value if late else early) / (busy * split + capture_time)"""),
("""        available, remaining, avoid = k.available, k.remaining, k.avoid
        capture_time = k.capture_time""", """        available, remaining, avoid = k.available, k.remaining, k.avoid
        capture_time = k.capture_time
        contested = k.contested"""),
("""        info = k.groups[self.target]
        camps = self.target_camps()
        if camps:
            self.engage(camps)
            return "engage"
""", """        info = k.groups[self.target]
        camps = self.target_camps()
        if self.stage(info, camps):
            return "stage"
        if camps:
            self.engage(camps)
            return "engage"
"""),
("""    def travel(self, goals):""", """    def stage(self, info, camps):
        \"\"\"Hold at the staging point of a contested target until enough of the team is with us.\"\"\"
        k = self.k
        assert k is not None
        now = cambc.round_number()
        if info.index not in k.contested or k.reward_ready[info.index]:
            self.staged = None
            return False
        me = cambc.me()
        position = me.position()
        # Already fighting it, or still far away: carry on as usual.
        if any(_alive(camp) and camp.health() < camp.max_health() for camp in camps):
            return False
        if max(abs(position.x - info.cx), abs(position.y - info.cy)) > SQUAD_RANGE:
            return False
        alive = sum(1 for claim in memory.read_claims() if claim is not None)
        need = min(SQUAD_SIZE, max(1, alive))
        near = 1 + sum(
            1
            for ally in cambc.vision.champions(Team.ALLY)
            if ally != me and _alive(ally) and position.chebyshev_distance(ally.position()) <= 5
        )
        if near >= need:
            self.staged = None
            return False
        if self.staged is None or self.staged[0] != info.index:
            self.staged = (info.index, now)
        if now - self.staged[1] > SQUAD_WAIT:
            return False
        point = k.staging[info.index]
        nav.step_towards(k, nav.tiles_around(point, 1) & ~k.spawn_tiles)
        return True

    def travel(self, goals):"""),
("""        self.bank_after = 0
""", """        self.bank_after = 0
        # (group index, round) when we started waiting for the squad at that group.
        self.staged = None
"""),
("""DEBUG = False
""", """DEBUG = False
# Squad play on contested groups: start staging within this range, wait for this many, for at most this long.
SQUAD_RANGE = 12
SQUAD_SIZE = 3
SQUAD_WAIT = 25
"""),
])
