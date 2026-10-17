import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("DEBUG = False", "DEBUG = True"), ("""        mode = self.decide()
        if DEBUG:""", """        mode = self.decide()
        if DEBUG:
            hp = {}
            for camp in cambc.vision.camps():
                g = int(camp.camp_group())
                hp[g] = hp.get(g, 0) + int(camp.health())
            print("H", cambc.round_number(), int(cambc.me()), sorted(hp.items()))""")])
