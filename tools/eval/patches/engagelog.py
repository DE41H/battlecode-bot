import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""        target = min(camps, key=lambda camp: camp.health())
        if combat.basic_attack(target):""", """        target = min(camps, key=lambda camp: camp.health())
        print("ENG", cambc.round_number(), int(me), position.x, position.y, [(c.position().x, c.position().y, c.health(), int(c.kind()), str(c.state()) if hasattr(c, "state") else "") for c in camps], me.attack_range(), me.can_move())
        if combat.basic_attack(target):""")])
