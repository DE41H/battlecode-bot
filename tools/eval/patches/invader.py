import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Sparring partner: hunt as one pack (full camp-damage term clumps the team) in the opponent's half.
edit(D + "knowledge.py", [
("""        recall = cambc.constants.RECALL_TIME
        table = []
        for info in self.groups:""", """        recall = cambc.constants.RECALL_TIME
        enemy = self.enemy_spawn.positions()
        ex = sum(p.x for p in enemy) // len(enemy)
        ey = sum(p.y for p in enemy) // len(enemy)
        table = []
        for info in self.groups:
            raid = 2.0 if max(abs(info.cx - ex), abs(info.cy - ey)) < info.spawn_distance else 1.0"""),
("""                    info.gems + 0.35 * info.gold,
                    info.gems + 0.1 * info.gold if info.gems > 0 else 0.0,""", """                    raid * (info.gems + 0.35 * info.gold),
                    raid * (info.gems + 0.1 * info.gold) if info.gems > 0 else 0.0,"""),
])
edit(D + "bot.py", [("+ 0.25 * strength * kill / team / budget * trip_cost", "+ strength * kill / team / budget * trip_cost")])
