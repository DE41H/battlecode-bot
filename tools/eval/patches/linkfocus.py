import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Killing either of Cassi and Issac kills both, so their health counts half.
edit(D + "bot.py", [("""        target = min(worth, key=lambda enemy: enemy.health())
        acted = combat.cast_damage([target])""", """        target = min(
            worth,
            key=lambda enemy: enemy.health()
            / (2.0 if enemy.champion_name() in (Kind.CASSI, Kind.ISSAC) else 1.0),
        )
        acted = combat.cast_damage([target])""")])
