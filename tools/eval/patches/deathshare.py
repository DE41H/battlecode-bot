import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit, append
# One ally killed by enemies at a camp warns the whole team off it, instead of everyone feeding the same spot in turn.
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
("AMBUSH_BACKOFF = 10\n", "AMBUSH_BACKOFF = 10\n# Rounds we avoid the group we were going for when enemies killed us.\nDEATH_BACKOFF = 120\n"),
("""        self.last_health = None
        self.bank_after = 0
""", """        self.last_health = None
        self.bank_after = 0
        self.saw_enemies = False
"""),
("""        if not me.is_alive():
            self.healing = False
            self.target = None""", """        if not me.is_alive():
            if self.target is not None and self.saw_enemies:
                memory.mark_death(self.target)
                k.avoid[self.target] = max(
                    k.avoid[self.target], cambc.round_number() + DEATH_BACKOFF
                )
            self.saw_enemies = False
            self.healing = False
            self.target = None"""),
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        self.saw_enemies = bool(enemies)
"""),
("""        late = now >= 700
        available, remaining, avoid = k.available, k.remaining, k.avoid""", """        late = now >= 700
        deadly = memory.death_group()
        available, remaining, avoid = k.available, k.remaining, k.avoid"""),
("""            if index == current:
                score *= 1.15""", """            if index == current:
                score *= 1.15
            if index == deadly:
                score *= 0.2"""),
])
