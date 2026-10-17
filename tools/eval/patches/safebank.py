import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "knowledge.py", [("""        for info in self.groups:
            info.altar_distance""", """        enemy = self.enemy_spawn.positions()
        self.enemy_center = cambc.Vec2(
            sum(p.x for p in enemy) // len(enemy), sum(p.y for p in enemy) // len(enemy)
        )
        # Extra walking we accept to bank at an altar on our side of the map rather than theirs.
        self.altar_risk = [
            max(
                0,
                a.chebyshev_distance(self.spawn_center)
                - a.chebyshev_distance(self.enemy_center),
            )
            // 2
            for a in self.altars
        ]
        for info in self.groups:
            info.altar_distance""")])
edit(D + "bot.py", [("""        goals = cambc.Bitboard()
        for altar in altars:
            goals |= nav.tiles_around(altar, reach)
        nav.step_towards(self.k, goals)
""", """        k = self.k
        assert k is not None
        enemies = [
            enemy.position()
            for enemy in cambc.vision.champions(Team.ENEMY)
            if _alive(enemy)
        ]

        # Prefer altars on our side and away from enemies we can see; a longer walk beats dying with the bag.
        def cost(altar):
            risk = k.altar_risk[k.altars.index(altar)] if altar in k.altars else 0
            if any(altar.chebyshev_distance(enemy) <= 6 for enemy in enemies):
                risk += 25
            return position.chebyshev_distance(altar) + risk

        goals = nav.tiles_around(min(altars, key=cost), reach)
        avoid = cambc.Bitboard()
        for enemy in enemies:
            avoid.draw_chebyshev(enemy, 3)
        avoid.set(position, False)
        if not nav.step_towards(k, goals, avoid):
            nav.step_towards(k, goals)
""")])
