import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# On top of squad: only monolith-strength groups count as contested, so ordinary farming stays solo.
edit(D + "knowledge.py", [
("""            if theirs <= ours * CONTESTED:""", """            if theirs <= ours * CONTESTED and info.strength >= SQUAD_STRENGTH:"""),
("""SQUAD_BACK = 9
""", """SQUAD_BACK = 9
# Only groups at least this strong (a monolith is 200) are taken as a squad.
SQUAD_STRENGTH = 200
"""),
])
