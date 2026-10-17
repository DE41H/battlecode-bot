import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# A walk to the altar costs the same for any bag, so carry more when the altar is far and less when it is close.
edit(D + "bot.py", [("""        if gems >= BANK_GEMS:
            return True""", """        if gems >= min(120, 20 + 4 * altar_distance):
            return True""")])
