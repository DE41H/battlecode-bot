import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("busy = travel + kill + strength * kill / team / budget * trip_cost + fixed",
                     "busy = travel + kill + 0.35 * strength * kill / team / budget * trip_cost + fixed")])
