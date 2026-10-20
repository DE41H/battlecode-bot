import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [("""+ 0.25 * strength * kill / team / budget * trip_cost""", """+ 0.4 * strength * kill / team / budget * trip_cost""")])
