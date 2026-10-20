import os
import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Last stand only when it can kill: a traced 01corridors game showed fight -> last-stand -> death as the commonest
# path to a champion kill. Trade back only against an enemy within STAND_BURSTS of our burst; otherwise keep
# backing away.
BURSTS = os.environ.get("STAND_BURSTS", "2.0")
edit(D + "bot.py", [
("""            pressing = [
                enemy
                for enemy in enemies
                if position.chebyshev_distance(enemy.position())
                <= enemy.attack_range() + 1
            ]
            if pressing and self.fight_enemies(pressing, aggressive=True):""", f"""            burst = combat.burst_estimate(me) * {BURSTS}
            pressing = [
                enemy
                for enemy in enemies
                if position.chebyshev_distance(enemy.position())
                <= enemy.attack_range() + 1
                and enemy.health() <= burst
            ]
            if pressing and self.fight_enemies(pressing, aggressive=True):"""),
])
