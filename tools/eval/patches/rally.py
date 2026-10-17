import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit, append
edit(D + "memory.py", [("CLAIM_SLOTS = 8\n", '''CLAIM_SLOTS = 6
# Bytes 6-7: the 7-tile cell where an ally is fighting (plus one, 0 for none) and the round it was called.
RALLY = 6
RALLY_CELL = 7
RALLY_ROUNDS = 3
''')])
append(D + "memory.py", '''

def call_rally(position):
    cambc.shared_memory[RALLY] = (
        1 + (position.x // RALLY_CELL) * 16 + position.y // RALLY_CELL
    )
    cambc.shared_memory[RALLY + 1] = cambc.round_number() & 255


def read_rally():
    """Centre of the cell where an ally recently called for help, or None."""
    data = bytearray(2)
    cambc.shared_memory.read(RALLY, data)
    if data[0] == 0 or (cambc.round_number() - data[1]) & 255 > RALLY_ROUNDS:
        return None
    cell = data[0] - 1
    half = RALLY_CELL // 2
    return cambc.Vec2(
        (cell >> 4) * RALLY_CELL + half, (cell & 15) * RALLY_CELL + half
    )
''')
edit(D + "bot.py", [
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        if any(position.chebyshev_distance(e.position()) <= 6 for e in enemies):
            memory.call_rally(position)
"""),
("""        if self.should_bank(enemies):
            self.bank()
            return "bank"
""", """        if self.should_bank(enemies):
            self.bank()
            return "bank"

        # Join a nearby fight an ally called, unless we carry gems or are already hurt.
        rally = memory.read_rally()
        if (
            rally is not None
            and not enemies
            and me.gem_count() < 30
            and me.health() >= me.max_health() * 0.6
            and 3 < position.chebyshev_distance(rally) <= RALLY_REACH
        ):
            self.travel(nav.tiles_around(rally, 2))
            return "rally"
"""),
("CANDIDATES = 3\n", """CANDIDATES = 3
# How far we walk to answer an ally's call for help.
RALLY_REACH = 14
"""),
])
