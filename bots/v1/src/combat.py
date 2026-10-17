"""Combat micro shared by camp farming and opportunistic fights."""

import contextlib

import cambc

Team = cambc.Team


def _in_range(me, target, reach):
    return me.position().chebyshev_distance(target.position()) <= reach


def _alive(target):
    try:
        return target.is_visible() and target.health() > 0
    except cambc.Error:
        return False


def basic_attack(target):
    """Hit the target with a basic attack, chaining an attack reset if we have one ready."""
    me = cambc.me()
    if not me.can_attack() or not _alive(target):
        return False
    if not me.attack_tiles().is_set(target.position()):
        return False
    me.attack(target)
    for ability in me.abilities():
        if ability.is_attack_reset() and _alive(target) and ability.is_ready():
            try:
                ability.use()
            except cambc.Error:
                continue
            if me.can_attack() and _alive(target):
                me.attack(target)
            break
    return True


def cast_damage(targets, allow_exclusive=True):
    """Cast our strongest ready damaging spell on the most valuable target in range."""
    me = cambc.me()
    best = None
    for ability in me.abilities():
        if not (ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()):
            continue
        info = ability.info()
        if info is None or not ability.is_ready():
            continue
        if info.exclusive_with_movement and not allow_exclusive:
            continue
        modifier = getattr(info, "modifier", 0.0)
        if modifier <= 0 and not ability.is_cc():
            continue
        reach = int(getattr(info, "range", 0))
        for target in targets:
            if not _alive(target) or not _in_range(me, target, reach):
                continue
            # Prefer damage, then the lowest-health target so kills land sooner.
            key = (modifier, -target.health())
            if best is None or key > best[0]:
                best = (key, ability, target)
    if best is None:
        return False
    _, ability, target = best
    try:
        if ability.is_aoe_damage():
            return ability.use(target.position())
        return ability.use(target)
    except cambc.Error:
        return False


def support_spells(knowledge, under_fire):
    """Self-shields and ally heals; these never cost a move."""
    me = cambc.me()
    for ability in me.abilities():
        if not ability.is_ready():
            continue
        try:
            if ability.is_shield() and under_fire:
                ability.use()
                return
            if ability.is_heal():
                info = ability.info()
                reach = int(getattr(info, "range", 4))
                hurt = [
                    ally
                    for ally in cambc.vision.champions(Team.ALLY)
                    if ally != me
                    and _in_range(me, ally, reach)
                    and ally.max_health() - ally.health() >= ability.heal_amount()
                ]
                if hurt:
                    ability.use(
                        min(hurt, key=lambda ally: ally.health() / ally.max_health())
                    )
                    return
        except cambc.Error:
            continue


def burst_estimate(me):
    """Damage we can deal this turn: basic attack(s) plus the best ready spell."""
    damage = me.strength()
    best_spell = 0.0
    for ability in me.abilities():
        if ability.is_attack_reset() and ability.is_ready():
            damage += me.strength()
        elif ability.is_ready() and (
            ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()
        ):
            with contextlib.suppress(cambc.Error):
                best_spell = max(best_spell, ability.damage_amount())
    return damage + best_spell


def sustained_damage(me):
    """Average damage per turn against camps, used to estimate clear times."""
    damage = me.strength()
    for ability in me.abilities():
        info = ability.info()
        if info is None:
            continue
        if ability.is_attack_reset():
            damage += me.strength() / max(1, info.max_cooldown)
        elif ability.is_damage() or ability.is_aoe_damage() or ability.is_cc():
            damage += (
                me.focus() * getattr(info, "modifier", 0.0) / max(1, info.max_cooldown)
            )
    if me.champion_name() == cambc.ChampionType.VARG:
        damage *= 1.5
    with contextlib.suppress(cambc.Error):
        damage *= me.base_stats().camp_damage_multiplier
    return max(damage, 1.0)


def fighting_power(champions):
    """Lanchester-style strength of a group: total health times total damage output."""
    health = sum(max(0.0, champion.health()) for champion in champions)
    damage = sum(
        champion.strength() + 0.25 * champion.focus() for champion in champions
    )
    return health * damage


def local_advantage(enemies, radius=6):
    """Our power over theirs within radius of us, and the enemies counted; ratio is None with no enemies."""
    me = cambc.me()
    position = me.position()
    near = [
        enemy
        for enemy in enemies
        if position.chebyshev_distance(enemy.position()) <= radius
    ]
    if not near:
        return None, near
    allies = [me] + [
        ally
        for ally in cambc.vision.champions(Team.ALLY)
        if ally != me
        and _alive(ally)
        and position.chebyshev_distance(ally.position()) <= radius
    ]
    return fighting_power(allies) / max(1.0, fighting_power(near)), near
