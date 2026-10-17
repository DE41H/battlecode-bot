import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Cassi and Issac share a pick (and its zone) but each needs its own claim byte.
edit(D + "bot.py", [
("""        self.slot = None
        self.target = None""", """        self.slot = None
        self.zone = None
        self.target = None"""),
("""        if self.slot is None:
            self.slot = int(me) % memory.CLAIM_SLOTS
""", """        if self.slot is None:
            self.slot = int(me) % memory.CLAIM_SLOTS
        self.zone = self.slot
        if me.champion_name() == Kind.ISSAC and len(self.plan.picks) < memory.CLAIM_SLOTS:
            self.slot = len(self.plan.picks)
"""),
("my_zone, current = self.slot, self.target", "my_zone, current = self.zone, self.target"),
])
