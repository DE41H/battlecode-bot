import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("SHOP_GOLD = 150", "SHOP_GOLD = 90")])
