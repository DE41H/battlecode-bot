import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Respawn waves: a dead champion publishes when it will respawn (claim byte >= 200 = respawning in (v - 200) * 4
# rounds), and a champion on spawn waits for any ally due back within WAVE_WAIT rounds, so the team leaves spawn
# together instead of walking into a held objective one at a time.
edit(D + "memory.py", [
("""def read_claims():
    data = bytearray(CLAIM_SLOTS)
    cambc.shared_memory.read(0, data)
    return [value - 1 if value else None for value in data]
""", """# Claim byte values from RESPAWNING up mean "dead, back in (value - RESPAWNING) * 4 rounds".
RESPAWNING = 200


def _raw_claims():
    data = bytearray(CLAIM_SLOTS)
    cambc.shared_memory.read(0, data)
    return data


def read_claims():
    return [value - 1 if 0 < value < RESPAWNING else None for value in _raw_claims()]


def write_respawn(slot, rounds_left):
    if slot is None or not 0 <= slot < CLAIM_SLOTS:
        return
    cambc.shared_memory[slot] = RESPAWNING + max(0, min(55, (rounds_left + 3) // 4))


def respawning_within(rounds, own_slot):
    \"\"\"Whether another slot's champion is dead and due back within this many rounds.\"\"\"
    for slot, value in enumerate(_raw_claims()):
        if slot != own_slot and value >= RESPAWNING and (value - RESPAWNING) * 4 <= rounds:
            return True
    return False
"""),
])
edit(D + "bot.py", [
("""        if not me.is_alive():
            self.healing = False
            self.target = None
            self.last_health = None
            memory.write_claim(self.slot, None)
            shop()
            return "dead"
""", """        if not me.is_alive():
            self.healing = False
            self.target = None
            self.last_health = None
            now = cambc.round_number()
            if self.died_at is None:
                self.died_at = now
            memory.write_respawn(
                self.slot, self.died_at + cambc.constants.RESPAWN_TIME - now
            )
            shop()
            return "dead"
        if self.died_at is not None:
            self.died_at = None
            self.wave_since = cambc.round_number()
            memory.write_claim(self.slot, None)
"""),
("""        # Stay on spawn after a recall until healed.
        if at_spawn and self.healing and me.health() < me.max_health() * HEALED:
            return "heal"
        self.healing = False
""", """        # Stay on spawn after a recall until healed.
        if at_spawn and self.healing and me.health() < me.max_health() * HEALED:
            return "heal"
        self.healing = False

        # Leave spawn in a wave: wait for allies about to respawn (capped, so nobody waits forever).
        if (
            at_spawn
            and me.gem_count() == 0
            and cambc.round_number() - self.wave_since <= WAVE_CAP
            and memory.respawning_within(WAVE_WAIT, self.slot)
            and not cambc.vision.champions(Team.ENEMY)
        ):
            return "wave"
"""),
("""        self.bank_after = 0
""", """        self.bank_after = 0
        # Round we were first seen dead, and the round we last came back (for respawn waves).
        self.died_at = None
        self.wave_since = -1000
"""),
("""DEBUG = False
""", """DEBUG = False
# Respawn waves: wait on spawn for allies due back within WAVE_WAIT rounds, for at most WAVE_CAP after respawning.
WAVE_WAIT = 15
WAVE_CAP = 40
"""),
])
