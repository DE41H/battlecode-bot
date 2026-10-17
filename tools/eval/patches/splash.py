import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Varg's basic attack splashes radius 1 and area spells hit radius 1: aim both at the middle of a pack.
edit(D + "bot.py", [
("""        target = min(camps, key=lambda camp: camp.health())
        if combat.basic_attack(target):""", """        if me.champion_name() == Kind.VARG:
            target = max(
                camps,
                key=lambda camp: (combat.neighbours(camp, camps, 1), -camp.health()),
            )
        else:
            target = min(camps, key=lambda camp: camp.health())
        if combat.basic_attack(target):"""),
])
edit(D + "combat.py", [
("""        reach = int(getattr(info, "range", 0))
        for target in targets:
            if not _alive(target) or not _in_range(me, target, reach):
                continue
            # Prefer damage, then the lowest-health target so kills land sooner.
            key = (modifier, -target.health())""", """        reach = int(getattr(info, "range", 0))
        radius = int(getattr(info, "radius", 0)) if ability.is_aoe_damage() else 0
        for target in targets:
            if not _alive(target) or not _in_range(me, target, reach):
                continue
            # Prefer total damage (area spells count every target they hit), then the lowest-health target.
            hits = 1 + (neighbours(target, targets, radius) if radius else 0)
            key = (modifier * hits, -target.health())"""),
("""def support_spells(knowledge, under_fire):""", """def neighbours(target, units, radius):
    \"\"\"Other living units within radius of target: what a splash or area hit on it also reaches.\"\"\"
    position = target.position()
    return sum(
        1
        for unit in units
        if unit != target
        and _alive(unit)
        and position.chebyshev_distance(unit.position()) <= radius
    )


def support_spells(knowledge, under_fire):"""),
])
