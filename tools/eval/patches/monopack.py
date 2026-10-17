import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Monoliths (and whoever guards them) eat lone champions: gather three of us first, then go in together.
edit(D + "knowledge.py", [("""        camps = group.camps()
        self.max_health = sum(""", """        camps = group.camps()
        self.monolith = any(camp.kind() == cambc.CampType.MONOLITH for camp in camps)
        self.max_health = sum(""")])
edit(D + "bot.py", [
("AMBUSH_BACKOFF = 10\n", """AMBUSH_BACKOFF = 10
# Champions that must be near a monolith before anyone engages it, and how long we wait for them.
PACK = 3
PACK_WAIT = 40
"""),
("""        self.last_health = None
        self.bank_after = 0
""", """        self.last_health = None
        self.bank_after = 0
        self.staged_since = None
        self.engaged = None
"""),
("""        info = k.groups[self.target]
        camps = self.target_camps()
        if camps:
            self.engage(camps)
            return "engage\"""", """        info = k.groups[self.target]
        if info.monolith and self.engaged != self.target and not self.pack_ready(info):
            return self.stage(info)
        self.staged_since = None
        camps = self.target_camps()
        if camps:
            self.engaged = self.target
            self.engage(camps)
            return "engage\""""),
("""    def travel(self, goals):""", """    def pack_ready(self, info):
        me = cambc.me()
        near = 1 + sum(
            1
            for ally in cambc.vision.champions(Team.ALLY)
            if ally != me
            and _alive(ally)
            and ally.position().chebyshev_distance(info.center) <= 8
        )
        return near >= PACK

    def stage(self, info):
        \"\"\"Hold just outside a monolith's reach until enough of us arrive, or give it up.\"\"\"
        k = self.k
        assert k is not None
        now = cambc.round_number()
        if self.staged_since is None:
            self.staged_since = now
        if now - self.staged_since > PACK_WAIT:
            k.avoid[info.index] = now + PACK_WAIT
            self.target = None
            self.staged_since = None
            return "unstage"
        hold = nav.tiles_around(info.center, 7) & ~nav.tiles_around(info.center, 5)
        if not hold.is_set(cambc.me().position()):
            self.travel(hold)
        return "stage"

    def travel(self, goals):"""),
])
