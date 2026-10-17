import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "knowledge.py", [("""            if info.has_monolith:
                continue
""", "")])
