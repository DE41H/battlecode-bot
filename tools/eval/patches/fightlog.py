import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: full DEBUG trace in rounds 10-60 only (the opening fight), plus each visible enemy's id, hp and distance.
edit(D + "bot.py", [("DEBUG = False", "DEBUG = True"), ("""        if DEBUG:""", """        if DEBUG and 10 <= cambc.round_number() <= 60:"""),
("""                mode,
            )""", """                mode,
                [(int(e), int(e.health()), me.position().chebyshev_distance(e.position())) for e in cambc.vision.champions(Team.ENEMY) if e.is_visible()],
            )""")])
