import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, append
# Probe: inclusive fuel per function (calls, total), printed by every champion every 500 rounds and at the end.
append(D + "bot.py", '''

_PROF = {}


def _wrap(owner, name, label):
    inner = getattr(owner, name)

    def wrapped(*args, **kwargs):
        before = cambc.fuel_remaining()
        try:
            return inner(*args, **kwargs)
        finally:
            spent = before - cambc.fuel_remaining()
            calls, total = _PROF.get(label, (0, 0))
            _PROF[label] = (calls + 1, total + spent)

    setattr(owner, name, wrapped)


import knowledge as _knowledge
import shop as _shop
for _name in ("decide", "choose_target", "farm", "engage", "capture", "travel", "bank", "should_bank", "fight_enemies", "target_camps", "place_altar_lock"):
    _wrap(Bot, _name, _name)
_wrap(_knowledge.Knowledge, "observe", "observe")
_wrap(_knowledge.Knowledge, "open_altars", "open_altars")
_wrap(nav, "step_towards", "step_towards")
_wrap(nav, "step_away", "step_away")
_wrap(nav, "dash_towards", "dash_towards")
_wrap(combat, "local_advantage", "local_advantage")
_wrap(combat, "cast_damage", "cast_damage")
_wrap(combat, "support_spells", "support_spells")
_original_play = Bot.play_turn


def _play(self):
    _original_play(self)
    now = cambc.round_number()
    if now % 500 == 0 or now == 1999:
        print("PROF", now, int(cambc.me()), sorted(((v[1] // 1000, v[0], k) for k, v in _PROF.items()), reverse=True))


Bot.play_turn = _play
''')
