import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit, append
# Spread out to farm while the map is quiet; when an ally meets an enemy group, the whole team packs up.
edit(D + "memory.py", [("CLAIM_SLOTS = 8\n", '''CLAIM_SLOTS = 6
# Bytes 6-7: round (mod 256) an ally last saw an enemy group, and whether it ever did.
THREAT = 6
THREAT_ROUNDS = 60
''')])
append(D + "memory.py", '''

def mark_threat():
    cambc.shared_memory[THREAT] = cambc.round_number() & 255
    cambc.shared_memory[THREAT + 1] = 1


def under_threat():
    data = bytearray(2)
    cambc.shared_memory.read(THREAT, data)
    return data[1] == 1 and (cambc.round_number() - data[0]) & 255 < THREAT_ROUNDS
''')
edit(D + "bot.py", [
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        if (
            sum(1 for e in enemies if position.chebyshev_distance(e.position()) <= 8)
            >= 2
        ):
            memory.mark_threat()
"""),
("""        late = now >= 700
        available, remaining, avoid = k.available, k.remaining, k.avoid""", """        late = now >= 700
        share = 1.0 if memory.under_threat() else 0.25
        available, remaining, avoid = k.available, k.remaining, k.avoid"""),
("""                + 0.25 * strength * kill / team / budget * trip_cost""", """                + share * strength * kill / team / budget * trip_cost"""),
])
