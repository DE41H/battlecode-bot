import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("PRESS_EDGE = 0.5", "PRESS_EDGE = 0.35")])
