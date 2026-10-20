import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# DEBUG trace only every 50th round, so the probe's fuel use (and so its game) stays close to the real bot's.
edit(D + "bot.py", [("DEBUG = False", "DEBUG = True"), ("""        mode = self.decide()
        if DEBUG:""", """        mode = self.decide()
        if DEBUG and cambc.round_number() % 50 == 0:""")])
