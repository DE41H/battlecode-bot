import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Camps die one by one and spread their hits, so a kill costs about a quarter of strength x kill time.
edit(D + "bot.py", [("busy = travel + kill + strength * kill / team / budget * trip_cost + fixed",
                     "busy = travel + kill + 0.25 * strength * kill / team / budget * trip_cost + fixed")])
