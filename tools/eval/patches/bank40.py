import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("BANK_GEMS = 60", "BANK_GEMS = 40")])
