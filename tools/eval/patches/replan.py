import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Spend more fuel on target choice: re-plan every 3 rounds instead of 10 and refine 6 candidates with real walking
# distance instead of 3 (median turn used only 0.71M of 2.5M).
edit(D + "bot.py", [
("""            or (now % 10 == int(cambc.me()) % 10 and cambc.fuel_remaining() > 1_500_000)""",
 """            or (now % 3 == int(cambc.me()) % 3 and cambc.fuel_remaining() > 1_300_000)"""),
("""CANDIDATES = 3""", """CANDIDATES = 6"""),
])
