import os
import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Camps do not chase but keep hitting until we are out of their range, so only stay while we can absorb every
# hit on the way out: health > incoming x (steps to leave range + MARGIN). Then drop the group for a while.
# Platform: 8 of our 22 deaths a game were to camps, 20 a game on 00rows (Varg died at the monolith pair
# every ~112 rounds); the old check (health < 2 x awake strength) let melee champions die walking out.
MARGIN = int(os.environ.get("CS_MARGIN", "1"))
BACKOFF = int(os.environ.get("CS_BACKOFF", "20"))
edit(D + "bot.py", [
("""        # Back off before a camp kills us; it falls asleep two rounds after we leave.
        incoming = sum(
            camp.strength()
            for camp in camps
            if _alive(camp) and camp.health() < camp.max_health()
        )
        if incoming > 0 and me.health() < incoming * 2:
            nav.step_away(self.k, [camp.position() for camp in camps], 4)
            return
""", f"""        # Camps do not chase but hit until we leave their range, so stay only while we can take every hit
        # on the way out. Hitting the target wakes all of it; other camps count once awake (damaged).
        reach = me.attack_range()
        incoming, escape, threats = 0.0, 1, []
        for camp, index, hp in self.k.seen:
            if hp <= 0:
                continue
            strength = camp.strength()
            if strength <= 0 or (index != self.target and hp >= camp.max_health()):
                continue
            span = camp.attack_range() + 1
            distance = position.chebyshev_distance(camp.position())
            if index != self.target and distance > span:
                continue
            incoming += strength
            threats.append(camp.position())
            escape = max(escape, span - min(distance, reach))
        if incoming > 0 and me.health() <= incoming * (escape + {MARGIN}):
            nav.step_away(self.k, threats, 4)
            if {BACKOFF} > 0 and self.target is not None:
                self.k.avoid[self.target] = cambc.round_number() + {BACKOFF}
                self.target = None
            return
"""),
])
