import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Robustness: skip enemies that left vision earlier in the turn, and never let a refused recall (stunned:
# "Champion cannot act") abort the whole turn.
edit(D + "bot.py", [
("""        worth = []
        for enemy in enemies:
            try:
                gems = enemy.gem_count()""", """        worth = []
        for enemy in enemies:
            if not _alive(enemy):
                continue
            try:
                gems = enemy.gem_count()"""),
("""            if not threats:
                me.recall()
                self.healing = True
                return "low-recall\"""", """            if not threats:
                try:
                    me.recall()
                except cambc.Error:
                    return "stunned"
                self.healing = True
                return "low-recall\""""),
("""                for enemy in near
                if position.chebyshev_distance(enemy.position())
                <= max(enemy.attack_range(), 4) + 1""", """                for enemy in near
                if _alive(enemy)
                and position.chebyshev_distance(enemy.position())
                <= max(enemy.attack_range(), 4) + 1"""),
])
