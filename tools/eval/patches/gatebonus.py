import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# While every altar is shut, the gate group (01boss-battle's monoliths) is worth far more than its own reward.
edit(D + "bot.py", [("""        available, remaining, avoid = k.available, k.remaining, k.avoid
""", """        available, remaining, avoid = k.available, k.remaining, k.avoid
        gate_bonus = 3.0 if not k.open_altars() else 1.0
"""), ("""            if index == current:
                score *= 1.15""", """            if index == current:
                score *= 1.15
            if index in k.gates:
                score *= gate_bonus""")])
