import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Bank at the nearest open altar even when it carries an enemy lock: tributing there auto-attacks the lock (3 hits).
# Skipping locked altars made champions oscillate, because has_altar_lock() is False whenever the altar is out of
# view: they turned back toward a far altar on seeing the lock and back toward the locked one a step later.
edit(D + "bot.py", [("""    def usable_altars(self):
        \"\"\"Open altars without an enemy lock (all open ones if every one is locked), as indices into k.altars.\"\"\"
        k = self.k
        assert k is not None
        open_altars = k.open_altars()
        altars = []
        for i in open_altars:
            altar = k.altars[i]
            try:
                if (
                    cambc.vision.has_altar_lock(altar)
                    and cambc.vision.altar_lock_at(altar).is_enemy()
                ):
                    continue
            except cambc.Error:
                pass
            altars.append(i)
        return altars or open_altars
""", """    def usable_altars(self):
        \"\"\"Open altars, as indices into k.altars; an enemy lock costs only three hits, so locked ones count too.\"\"\"
        k = self.k
        assert k is not None
        return k.open_altars()
""")])
