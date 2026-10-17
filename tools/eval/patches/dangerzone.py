import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit, append
# Shared bytes 6-7: the 7-tile cell where an ally last saw two or more enemies together, and when.
edit(D + "memory.py", [("CLAIM_SLOTS = 8\n", '''CLAIM_SLOTS = 6
DANGER = 6
DANGER_CELL = 7
DANGER_ROUNDS = 20
''')])
append(D + "memory.py", '''

def mark_danger(position):
    cambc.shared_memory[DANGER] = (
        1 + (position.x // DANGER_CELL) * 16 + position.y // DANGER_CELL
    )
    cambc.shared_memory[DANGER + 1] = cambc.round_number() & 255


def read_danger():
    """Centre (x, y) of the cell where allies recently saw an enemy group, or None."""
    data = bytearray(2)
    cambc.shared_memory.read(DANGER, data)
    if data[0] == 0 or (cambc.round_number() - data[1]) & 255 > DANGER_ROUNDS:
        return None
    cell = data[0] - 1
    half = DANGER_CELL // 2
    return ((cell >> 4) * DANGER_CELL + half, (cell & 15) * DANGER_CELL + half)
''')
edit(D + "bot.py", [
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        if len(enemies) >= 2:
            memory.mark_danger(enemies[0].position())
"""),
("""        late = now >= 700
        available, remaining, avoid = k.available, k.remaining, k.avoid""", """        late = now >= 700
        danger = memory.read_danger()
        available, remaining, avoid = k.available, k.remaining, k.avoid"""),
("""            if index == current:
                score *= 1.15""", """            if index == current:
                score *= 1.15
            # Keep lone farmers away from where an enemy group was just seen.
            if danger is not None and max(abs(cx - danger[0]), abs(cy - danger[1])) <= 8:
                score *= 0.4"""),
])
