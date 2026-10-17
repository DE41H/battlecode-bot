import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Enemies seen recently: they may be stalking us, so bank smaller bags instead of carrying them.
edit(D + "bot.py", [
("""        self.last_health = None
        self.bank_after = 0
""", """        self.last_health = None
        self.bank_after = 0
        self.enemy_seen = -1000
"""),
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        if enemies:
            self.enemy_seen = cambc.round_number()
"""),
("""        if gems >= 10 and enemies:
            return True""", """        if gems >= 10 and enemies:
            return True
        if gems >= 30 and cambc.round_number() - self.enemy_seen < 40:
            return True"""),
])
