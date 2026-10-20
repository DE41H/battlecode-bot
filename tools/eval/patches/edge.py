import os
import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Fight-entry thresholds from the environment (defaults are the shipped values).
edit(D + "bot.py", [
("FIGHT_EDGE = 0.8", f"FIGHT_EDGE = {os.environ.get('FIGHT_EDGE', '0.8')}"),
("RETREAT_EDGE = 0.9", f"RETREAT_EDGE = {os.environ.get('RETREAT_EDGE', '0.9')}"),
("PRESS_EDGE = 0.5", f"PRESS_EDGE = {os.environ.get('PRESS_EDGE', '0.5')}"),
])
