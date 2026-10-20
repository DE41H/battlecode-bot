import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# While every altar is shut behind a gate group, gems cannot score: keep valuing gold (the tiebreak).
edit(D + "bot.py", [("""        late = now >= 700
""", """        shut = not k.open_altars()
        late = now >= 700 and not shut
""")])
