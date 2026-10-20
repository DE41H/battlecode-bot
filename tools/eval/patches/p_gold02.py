import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "knowledge.py", [("""info.gems + 0.35 * info.gold""", """info.gems + 0.2 * info.gold""")])
