import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Dying at a target usually means enemies hold it; stay away well past our 60-round respawn.
edit(D + "bot.py", [
("AMBUSH_BACKOFF = 10\n", "AMBUSH_BACKOFF = 10\n# Rounds we avoid the group we were going for when we died.\nDEATH_BACKOFF = 120\n"),
("""        if not me.is_alive():
            self.healing = False
            self.target = None""", """        if not me.is_alive():
            if self.target is not None:
                k.avoid[self.target] = max(
                    k.avoid[self.target], cambc.round_number() + DEATH_BACKOFF
                )
            self.healing = False
            self.target = None"""),
])
