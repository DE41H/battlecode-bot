import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Never farm while an enemy can hit us. With enemies near but the power ratio below FIGHT_EDGE, champions without
# gems used to keep capturing and hitting camps next to the enemy team until low health (elk_arena: the side that
# lost the first brawl died ~90 times). Now an enemy within its reach of us is fought (odds >= PRESS_EDGE) or fled.
edit(D + "bot.py", [
("""        if self.fight_enemies(enemies):
            return "snipe"
""", """        if ratio is not None:
            pressing = [
                enemy
                for enemy in near
                if position.chebyshev_distance(enemy.position())
                <= max(enemy.attack_range(), 4) + 1
            ]
            if pressing:
                if ratio >= PRESS_EDGE and self.fight_enemies(pressing, aggressive=True):
                    return "pressed-fight"
                if ratio < PRESS_EDGE:
                    nav.step_away(k, [enemy.position() for enemy in near], 6)
                    return "pressed-retreat"
        if self.fight_enemies(enemies):
            return "snipe"
"""),
("""RETREAT_EDGE = 0.9
""", """RETREAT_EDGE = 0.9
# An enemy that can reach us is fought at this ratio or better, and fled below it.
PRESS_EDGE = 0.5
"""),
])
