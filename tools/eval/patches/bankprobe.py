import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: in rounds 600-620, print what bank() sees: usable altars, lock state, goal count and whether we moved.
edit(D + "bot.py", [("""        nav.step_towards(k, goals)

    # ------------------------------------------------------------------ PvP""", """        moved = nav.step_towards(k, goals)
        if 600 <= cambc.round_number() <= 620:
            locks = []
            for a in k.all_altars:
                try:
                    locks.append((a.x, a.y, cambc.vision.has_altar_lock(a)))
                except cambc.Error:
                    locks.append((a.x, a.y, "?"))
            print("BANK", cambc.round_number(), int(me), position.x, position.y, "altars", [(k.altars[i].x, k.altars[i].y) for i in altars],
                  "open", k.open_altars(), "locks", locks, "goals", goals.count(), "moved", moved, "canmove", me.can_move(), flush=True)

    # ------------------------------------------------------------------ PvP""")])
