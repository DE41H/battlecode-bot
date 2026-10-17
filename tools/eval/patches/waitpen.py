import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""            if wait > 0:
                busy += wait
""", """            if wait > 0:
                busy += 1.5 * wait
""")])
