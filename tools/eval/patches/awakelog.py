import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""        mode = self.decide()
        if DEBUG:""", """        mode = self.decide()
        if DEBUG and cambc.me().is_alive():
            aw = cambc.vision.awake_camp_tiles()
            here = cambc.me().position()
            near = [(p.x, p.y, int(cambc.game_map.camp(p).camp_group()) if True else 0) for p in aw.positions() if p.chebyshev_distance(here) <= 4]
            if near:
                print("AWAKE", cambc.round_number(), int(cambc.me()), here.x, here.y, near)
        if DEBUG:""")])
