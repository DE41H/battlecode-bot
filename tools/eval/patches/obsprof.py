import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: fuel split inside Knowledge.observe, printed every 500 rounds.
edit(D + "knowledge.py", [("""        self.seen = []
        health = {}
        for camp in cambc.vision.camps():""", """        global _OBS
        f0 = cambc.fuel_remaining()
        camps = cambc.vision.camps()
        f1 = cambc.fuel_remaining()
        self.seen = []
        health = {}
        for camp in camps:"""),
("""        me = cambc.me().position()
        # Our vision plus""", """        f2 = cambc.fuel_remaining()
        me = cambc.me().position()
        # Our vision plus"""),
("""        visible = cambc.vision.visible_tiles()
        for info in nearby:""", """        visible = cambc.vision.visible_tiles()
        f3 = cambc.fuel_remaining()
        _OBS[0] += f0 - f1; _OBS[1] += f1 - f2; _OBS[2] += f2 - f3; _OBS[4] += len(camps); _OBS[5] += 1
        if now % 500 == 0:
            print("OBS", now, int(cambc.me()), [v // max(1, _OBS[5]) for v in _OBS], flush=True)
        f4 = cambc.fuel_remaining()
        for info in nearby:"""),
("""class Knowledge:""", """_OBS = [0, 0, 0, 0, 0, 0]


class Knowledge:"""),
])
