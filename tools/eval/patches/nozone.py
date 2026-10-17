import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""            if zone == my_zone:
                score *= 1.3
            elif zone >= 0:
                score *= 0.85
""", "")])
