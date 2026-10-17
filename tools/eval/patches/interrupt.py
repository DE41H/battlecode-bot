import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "bot.py", [
("""        if self.place_altar_lock(enemies):
            pass
""", """        if self.place_altar_lock(enemies):
            pass
        self.interrupt(enemies)
"""),
("""    def place_altar_lock(self, enemies):""", '''    def interrupt(self, enemies):
        """Stun an enemy tribute or hit an enemy recall: either cancels their channel."""
        me = cambc.me()
        position = me.position()
        for enemy in sorted(enemies, key=lambda e: -e.gem_count()):
            try:
                tributing = enemy.is_submitting_gems()
                recalling = enemy.is_recalling()
            except cambc.Error:
                continue
            if not (tributing or recalling):
                continue
            distance = position.chebyshev_distance(enemy.position())
            for ability in me.abilities():
                if not ability.is_ready():
                    continue
                if not (
                    ability.is_cc()
                    or (recalling and (ability.is_damage() or ability.is_aoe_damage()))
                ):
                    continue
                info = ability.info()
                if info is None or distance > int(getattr(info, "range", 0)):
                    continue
                try:
                    if ability.can_target_ground() and ability.use(enemy.position()):
                        return True
                    if ability.can_target_enemies() and ability.use(enemy):
                        return True
                except cambc.Error:
                    continue
            if recalling and combat.basic_attack(enemy):
                return True
        return False

    def place_altar_lock(self, enemies):'''),
])
