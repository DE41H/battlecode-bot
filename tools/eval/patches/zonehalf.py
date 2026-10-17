import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Only split our own half of the map into zones; groups nearer the enemy spawn stay shared.
edit(D + "draft.py", [
("""    entries = []
    for group in groups:""", """    enemy = game_map.spawn_region(Team.ENEMY).positions()
    ex = sum(p.x for p in enemy) / len(enemy)
    ey = sum(p.y for p in enemy) / len(enemy)
    entries = []
    for group in groups:"""),
("""        cy = sum(p.y for p in tiles) / len(tiles)
        entries.append(""", """        cy = sum(p.y for p in tiles) / len(tiles)
        if max(abs(cx - ex), abs(cy - ey)) < max(abs(cx - sx), abs(cy - sy)):
            continue
        entries.append("""),
])
