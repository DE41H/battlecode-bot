import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit, append
# Allies killed by enemies at a camp: next time go in three at a time instead of one by one.
edit(D + "memory.py", [("CLAIM_SLOTS = 8\n", '''CLAIM_SLOTS = 6
# Bytes 6-7: camp group (plus one) where an ally was just killed by enemies, and the round (mod 256).
DEATH = 6
DEATH_ROUNDS = 80
''')])
append(D + "memory.py", '''

def mark_death(group_index):
    cambc.shared_memory[DEATH] = group_index + 1
    cambc.shared_memory[DEATH + 1] = cambc.round_number() & 255


def death_group():
    """Group an ally recently died at, or None; clears the marker once it is stale."""
    data = bytearray(2)
    cambc.shared_memory.read(DEATH, data)
    if data[0] == 0:
        return None
    if (cambc.round_number() - data[1]) & 255 > DEATH_ROUNDS:
        cambc.shared_memory[DEATH] = 0
        return None
    return data[0] - 1
''')
edit(D + "bot.py", [
("AMBUSH_BACKOFF = 10\n", "AMBUSH_BACKOFF = 10\n# Champions that must be near a group where allies were just killed before anyone engages it, and how long we wait.\nPACK = 3\nPACK_WAIT = 40\n"),
("""        self.last_health = None
        self.bank_after = 0
""", """        self.last_health = None
        self.bank_after = 0
        self.saw_enemies = False
        self.staged_since = None
        self.engaged = None
"""),
("""        if not me.is_alive():
            self.healing = False
            self.target = None""", """        if not me.is_alive():
            if self.target is not None and self.saw_enemies:
                memory.mark_death(self.target)
            self.saw_enemies = False
            self.healing = False
            self.target = None"""),
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        self.saw_enemies = bool(enemies)
"""),
("""        info = k.groups[self.target]
        camps = self.target_camps()
        if camps:
            self.engage(camps)
            return "engage\"""", """        info = k.groups[self.target]
        if (
            self.target == memory.death_group()
            and self.engaged != self.target
            and not self.pack_ready(info)
        ):
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
        \"\"\"Hold just outside a deadly group until enough of us arrive, or give it up for a while.\"\"\"
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
