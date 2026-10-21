import os
import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Replaces campsafe's strength-based check (apply to bots/v2 at 2ded1ca). That check summed every armed camp of
# the target group at full strength, so champions refused groups they could clear (only camps within range 3 hit,
# and Jungle/Durability cut camp damage by a third), and with the soft back-off they re-picked the same group
# forever: 01boss-battle froze for the whole game (0 gold as team A). Now: once camps hit us, stay only while
# health > measured damage x (steps out + 1); after such a retreat below MEND health, go home to heal; and
# avoided groups are skipped outright in target choice.
MEND = os.environ.get("CM_MEND", "0.6")
HARD = os.environ.get("CM_HARD", "1") == "1"
edit(D + "bot.py", [
("""        # Health at the start of our last turn, to measure damage taken since.
        self.last_health = None
""", """        # Health at the start of our last turn, to measure damage taken since.
        self.last_health = None
        self.damage = 0.0
        # Set after backing off a camp group hurt: heal at home before the next one.
        self.mend = False
"""),
("""        self.last_health = health
""", """        self.last_health = health
        self.damage = damage
"""),
("""        position = me.position()
        at_spawn = k.ally_spawn.is_set(position)
        if at_spawn or me.champion_name() == Kind.TAVI:
            shop()
""", """        position = me.position()
        at_spawn = k.ally_spawn.is_set(position)
        if at_spawn:
            self.mend = False
        if at_spawn or me.champion_name() == Kind.TAVI:
            shop()
"""),
("""        low = LINKED_LOW_HEALTH if linked else LOW_HEALTH
""", f"""        low = LINKED_LOW_HEALTH if linked else LOW_HEALTH
        if self.mend:
            low = max(low, {MEND})
"""),
("""        reach = me.attack_range()
        incoming, escape, threats = 0.0, 1, []
        for camp, index, hp in self.k.seen:
            if hp <= 0:
                continue
            strength = camp.strength()
            if strength <= 0 or (
                index != self.target and not self.k.awake.is_set(camp.position())
            ):
                continue
            span = camp.attack_range() + 1
            distance = position.chebyshev_distance(camp.position())
            if index != self.target and distance > span:
                continue
            incoming += strength
            threats.append(camp.position())
            escape = max(escape, span - min(distance, reach))
        if incoming > 0 and me.health() <= incoming * (escape + 1):
            nav.step_away(self.k, threats, 4)
            if self.target is not None:""", f"""        reach = me.attack_range()
        incoming, escape, threats = 0.0, 1, []
        for camp, _, hp in self.k.seen:
            if hp <= 0 or not self.k.awake.is_set(camp.position()):
                continue
            strength = camp.strength()
            span = camp.attack_range() + 1
            distance = position.chebyshev_distance(camp.position())
            if strength <= 0 or distance > span:
                continue
            incoming += strength
            threats.append(camp.position())
            escape = max(escape, span - min(distance, reach))
        # Measured damage already counts our items and which camps actually reach us.
        if threats and (
            me.health() <= incoming
            or (self.damage > 0 and me.health() <= self.damage * (escape + 1))
        ):
            nav.step_away(self.k, threats, 4)
            if me.health() < me.max_health() * {MEND}:
                self.mend = True
            if self.target is not None:"""),
])
if HARD:
    edit(D + "bot.py", [
    ("""            if late and late_value <= 0:
                continue
""", """            if late and late_value <= 0:
                continue
            if avoid[index] > now:
                continue
"""),
    ])
