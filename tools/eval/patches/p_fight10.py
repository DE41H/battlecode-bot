import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""FIGHT_EDGE = 0.8""", """FIGHT_EDGE = 1.0""")])
