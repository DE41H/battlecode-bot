"""Champion decisions: farm the best-value camps, capture, bank gems, shop, ward ahead, and never farm under fire."""

import math

import cambc
import combat
import memory
import nav
from knowledge import Knowledge
from shop import shop

Team, Kind, Consumable = cambc.Team, cambc.ChampionType, cambc.ConsumableType

BANK_GEMS = 60
NEAR_ALTAR = 5
LOW_HEALTH = 0.35
# Cassi and Issac die together, so either one falling costs both bodies and both bags.
LINKED_LOW_HEALTH = 0.5
HEALED = 0.9
# Local power ratios (ours / theirs) for taking or refusing a fight with enemy champions.
FIGHT_EDGE = 0.8
RETREAT_EDGE = 0.9
# An enemy that can reach us is fought at this ratio or better, and fled below it.
PRESS_EDGE = 0.5
# Turns we hold a contested capture before giving it up, and how long we then avoid it.
CONTEST_TURNS = 4
CONTEST_BACKOFF = 30
SHOP_GOLD = 150
CANDIDATES = 3
# Rounds we hold off banking after being hit by an attacker we cannot see.
AMBUSH_BACKOFF = 10
# Set True in a probe copy to trace decisions in the replay's stdout.
DEBUG = False
# Ward placement: minimum new tiles revealed, how much better a new spot must be, and fuel we keep in reserve.
WARD_MIN_GAIN = 6
WARD_SWITCH = 1.2
WARD_FUEL = 1_200_000


def _alive(unit):
    try:
        return unit.is_visible() and unit.health() > 0
    except cambc.Error:
        return False


class Bot:
    def __init__(self):
        self.k = None
        self.plan = None
        self.slot = None
        self.target = None
        self.healing = False
        self.contested = 0
        # Health at the start of our last turn, to measure damage taken since.
        self.last_health = None
        self.bank_after = 0

    def setup(self):
        me = cambc.me()
        self.k = Knowledge()
        self.plan = memory.Plan()
        self.slot = self.plan.slot_of(me.champion_name())
        if self.slot is None:
            self.slot = int(me) % memory.CLAIM_SLOTS

    # ------------------------------------------------------------------ turn

    def play_turn(self):
        mode = self.decide()
        # Last: moving the ward drops the old ward's vision, and units seen through it must not vanish mid-turn.
        me = cambc.me()
        if me.is_alive() and not self.k.ally_spawn.is_set(me.position()):
            self.place_ward()
        if DEBUG:
            me = cambc.me()
            print(
                cambc.round_number(),
                int(me),
                int(me.champion_name()),
                me.position().x,
                me.position().y,
                int(me.health()),
                me.gem_count(),
                me.gold_count(),
                self.target,
                len(cambc.vision.champions(Team.ENEMY)),
                len(cambc.vision.champions(Team.ALLY)),
                mode,
            )

    def decide(self):
        """Take this turn's actions; returns a short label of what we chose."""
        me = cambc.me()
        if self.k is None:
            self.setup()
        k = self.k
        assert k is not None
        k.observe()

        if not me.is_alive():
            self.healing = False
            self.target = None
            self.last_health = None
            memory.write_claim(self.slot, None)
            shop()
            return "dead"
        health = me.health()
        damage = (
            0.0 if self.last_health is None else max(0.0, self.last_health - health)
        )
        self.last_health = health

        if me.is_submitting_gems():
            # Damage does not stop a tribute, so a carrier under fire can die a turn short and hand the killer its whole bag.
            if damage > 0 and health <= damage * (me.remaining_channel_time() + 1):
                me.cancel_submit_gems()
                self.bank_after = cambc.round_number() + AMBUSH_BACKOFF
            else:
                return "channel"
        elif me.is_recalling() or me.is_teleporting():
            return "channel"

        position = me.position()
        at_spawn = k.ally_spawn.is_set(position)
        if at_spawn or me.champion_name() == Kind.TAVI:
            shop()

        # Stay on spawn after a recall until healed.
        if at_spawn and self.healing and me.health() < me.max_health() * HEALED:
            return "heal"
        self.healing = False

        enemies = [
            enemy for enemy in cambc.vision.champions(Team.ENEMY) if _alive(enemy)
        ]
        hostile_camps = [
            camp
            for camp, _, hp in k.seen
            if hp > 0 and camp.strength() > 0 and hp < camp.max_health()
        ]

        if self.place_altar_lock(enemies):
            pass

        # Hit by something we cannot see, such as an enemy in a bush: carry the bag away from it.
        if (
            damage > 0
            and me.gem_count() > 0
            and not at_spawn
            and not enemies
            and not any(
                position.chebyshev_distance(camp.position()) <= camp.attack_range()
                for camp in hostile_camps
            )
        ):
            self.bank_after = max(
                self.bank_after, cambc.round_number() + AMBUSH_BACKOFF
            )
            nav.step_towards(k, k.ally_spawn)
            return "ambushed"

        # Low health: recall if nothing can interrupt it, otherwise back off first.
        linked = me.champion_name() in (Kind.CASSI, Kind.ISSAC)
        low = LINKED_LOW_HEALTH if linked else LOW_HEALTH
        if not at_spawn and me.health() < me.max_health() * low:
            threats = [
                e.position()
                for e in enemies
                if position.chebyshev_distance(e.position()) <= 6
            ]
            threats += [
                c.position()
                for c in hostile_camps
                if position.chebyshev_distance(c.position()) <= 4
            ]
            if (
                me.gem_count() > 0
                and k.nearest_altar_distance(position) <= 2
                and not enemies
                and k.open_altars()
            ):
                self.bank()
                return "low-bank"
            if not threats:
                me.recall()
                self.healing = True
                return "low-recall"
            # Walking away from a chaser only feeds it free hits, so trade back while we still can.
            pressing = [
                enemy
                for enemy in enemies
                if position.chebyshev_distance(enemy.position())
                <= enemy.attack_range() + 1
            ]
            if pressing and self.fight_enemies(pressing, aggressive=True):
                return "last-stand"
            nav.step_away(k, threats, 4)
            return "low-flee"

        # Fight with a clear edge, back off from a clear disadvantage, otherwise only take kill shots.
        ratio, near = combat.local_advantage(enemies)
        if ratio is not None:
            if ratio >= FIGHT_EDGE and self.fight_enemies(near, aggressive=True):
                return "fight"
            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):
                nav.step_away(k, [enemy.position() for enemy in near], 6)
                return "retreat"
        if ratio is not None:
            pressing = [
                enemy
                for enemy in near
                if position.chebyshev_distance(enemy.position())
                <= max(enemy.attack_range(), 4) + 1
            ]
            if pressing:
                if ratio >= PRESS_EDGE and self.fight_enemies(pressing, aggressive=True):
                    return "pressed-fight"
                if ratio < PRESS_EDGE:
                    nav.step_away(k, [enemy.position() for enemy in near], 6)
                    return "pressed-retreat"
        if self.fight_enemies(enemies):
            return "snipe"

        if self.should_bank(enemies):
            self.bank()
            return "bank"

        # Recall to spend a pile of gold when we are not carrying anything to lose.
        if (
            not at_spawn
            and me.gem_count() == 0
            and me.gold_count() >= SHOP_GOLD
            and not hostile_camps
            and not enemies
            and me.champion_name() != Kind.TAVI
            and self.target_camps() == []
        ):
            me.recall()
            self.healing = True
            return "shop-recall"

        return self.farm()

    # ---------------------------------------------------------------- vision

    def place_ward(self):
        me = cambc.me()
        if me.ward_cooldown() > 0 or cambc.fuel_remaining() < WARD_FUEL:
            return False
        k = self.k
        assert k is not None
        try:
            mine = me.visible_tiles()
            # Placement tiles can include walls, where a ward has no vision at all.
            tiles = me.ward_placement_tiles() & ~k.walls
        except cambc.Error:
            return False
        hidden = ~mine
        bush = k.bushes & hidden
        ahead = k.enemy_half & hidden

        def gain(tile):
            try:
                seen = cambc.Ward.visible_tiles_from(tile)
            except cambc.Error:
                return 0
            return (
                (seen & hidden).count()
                + 2 * (seen & bush).count()
                + (seen & ahead).count()
            )

        current = 0
        for ward in me.ward_positions():
            current = max(current, gain(ward))
        position = me.position()
        best, best_gain = None, current * WARD_SWITCH + WARD_MIN_GAIN
        for tile in tiles.positions():
            # Only the outer ring reaches past our own sight; inner tiles see little we do not.
            if position.chebyshev_distance(tile) < 2:
                continue
            value = gain(tile)
            if value > best_gain:
                best, best_gain = tile, value
        if best is None:
            return False
        try:
            return me.place_ward(best)
        except cambc.Error:
            return False

    # --------------------------------------------------------------- banking

    def usable_altars(self):
        """Open altars without an enemy lock (all open ones if every one is locked), as indices into k.altars."""
        k = self.k
        assert k is not None
        open_altars = k.open_altars()
        visible = cambc.vision.visible_tiles()
        altars = []
        for i in open_altars:
            altar = k.altars[i]
            if visible.is_set(altar):
                try:
                    k.locked[i] = (
                        cambc.vision.has_altar_lock(altar)
                        and cambc.vision.altar_lock_at(altar).is_enemy()
                    )
                except cambc.Error:
                    k.locked[i] = False
            if not k.locked[i]:
                altars.append(i)
        return altars or open_altars

    def should_bank(self, enemies):
        me = cambc.me()
        gems = me.gem_count()
        if gems <= 0:
            return False
        k = self.k
        assert k is not None
        # Nowhere to tribute until a gate group dies: keep farming (and fighting the gate) instead.
        if not k.open_altars():
            return False
        assert k is not None
        position = me.position()
        altar_distance = k.nearest_altar_distance(position)
        rounds_left = cambc.constants.MAX_ROUNDS - cambc.round_number()
        if rounds_left < altar_distance * 1.4 + math.ceil(gems / 10) + 15:
            return True
        if cambc.round_number() < self.bank_after:
            return False
        if (
            cambc.global_submitted_gems(Team.ALLY) + gems
            >= cambc.constants.WINNING_GEMS
        ):
            return True
        if gems >= BANK_GEMS:
            return True
        if altar_distance <= NEAR_ALTAR and not self.target_camps():
            return True
        # Bank while our target respawns rather than idling with a full bag.
        if self.target is not None:
            waiting = k.available[self.target] - cambc.round_number()
            if waiting > 0 and waiting >= altar_distance:
                return True
        if gems >= 10 and enemies:
            return True
        return me.health() < me.max_health() * 0.5

    def bank(self):
        me = cambc.me()
        position = me.position()
        k = self.k
        assert k is not None
        reach = cambc.constants.SUBMIT_GEMS_RANGE
        altars = self.usable_altars()
        for i in altars:
            altar = k.altars[i]
            if position.chebyshev_distance(altar) <= reach:
                try:
                    me.submit_gems(altar)
                    return
                except cambc.Error:
                    continue
        goals = cambc.Bitboard()
        for i in altars:
            goals |= k.altar_spots[i]
        if goals.is_empty():
            for i in altars:
                goals |= nav.tiles_around(k.altars[i], reach)
        nav.step_towards(k, goals)

    # ------------------------------------------------------------------ PvP

    def fight_enemies(self, enemies, aggressive=False):
        """Take only fights we clearly win: kill shots and fat gem carriers, or anyone when aggressive."""
        me = cambc.me()
        if not enemies:
            return False
        position = me.position()
        burst = combat.burst_estimate(me)
        worth = []
        for enemy in enemies:
            try:
                gems = enemy.gem_count()
            except cambc.Error:
                gems = 0
            in_reach = position.chebyshev_distance(enemy.position()) <= max(
                me.attack_range(), 4
            )
            if not in_reach:
                continue
            if (
                aggressive
                or enemy.health() <= burst
                or (gems >= 20 and me.health() >= enemy.health() * 1.2)
            ):
                worth.append(enemy)
        if not worth:
            return False
        target = min(worth, key=lambda enemy: enemy.health())
        acted = combat.cast_damage([target])
        acted = combat.basic_attack(target) or acted
        if not acted and me.can_move():
            acted = nav.step_towards(
                self.k, nav.tiles_around(target.position(), me.attack_range())
            )
            combat.basic_attack(target)
        return acted

    def place_altar_lock(self, enemies):
        """Cancel an enemy tribute by locking its altar."""
        me = cambc.me()
        try:
            lock = me.consumables()[int(Consumable.ALTAR_LOCK)]
            if lock.count() <= 0:
                return False
        except cambc.Error:
            return False
        k = self.k
        assert k is not None
        position = me.position()
        for enemy in enemies:
            try:
                if not enemy.is_submitting_gems():
                    continue
            except cambc.Error:
                continue
            for altar in k.all_altars:
                if (
                    altar.chebyshev_distance(enemy.position())
                    > cambc.constants.SUBMIT_GEMS_RANGE
                ):
                    continue
                if position.chebyshev_distance(
                    altar
                ) > 2 or cambc.vision.has_altar_lock(altar):
                    continue
                try:
                    if lock.use(altar):
                        return True
                except cambc.Error:
                    continue
        return False

    # ---------------------------------------------------------------- farming

    def target_camps(self):
        if self.target is None:
            return []
        target = self.target
        return [camp for camp, index, hp in self.k.seen if index == target and hp > 0]

    def choose_target(self):
        me = cambc.me()
        k = self.k
        assert k is not None and self.plan is not None
        now = cambc.round_number()
        position = me.position()
        px, py = position.x, position.y
        dps = combat.sustained_damage(me)
        # Health we can spend per trip before retreating to heal.
        budget = me.max_health() * (1 - LOW_HEALTH)
        others_on = {}
        for slot, claim in enumerate(memory.read_claims()):
            if claim is not None and slot != self.slot:
                others_on[claim] = others_on.get(claim, 0) + 1
        # While every altar is shut behind a gate group, gems cannot score: keep valuing gold, the tiebreak.
        late = now >= 700 and bool(k.open_altars())
        available, remaining, avoid = k.available, k.remaining, k.avoid
        capture_time = k.capture_time
        current = self.target

        # Python costs ~3k fuel per loop iteration here, so the loop body uses precomputed tuples only.
        best_score, best_index, scored = -1.0, None, []
        for (
            index,
            cx,
            cy,
            early,
            late_value,
            trip_cost,
            fixed,
            strength,
            _zone,
        ) in k.scoring:
            if late and late_value <= 0:
                continue
            team = 1 + others_on.get(index, 0)
            kill = remaining[index] / (dps * team)
            travel = max(abs(cx - px), abs(cy - py)) * 1.25
            wait = max(available[index], avoid[index]) - now - travel
            # Camps die one at a time and spread their hits, so a clear costs well under strength x kill time
            # (0.4 is best on engine 1.0.0: 218/294 vs 202 at 0.25 and 180 at 0.15).
            busy = (
                travel
                + kill
                + 0.4 * strength * kill / team / budget * trip_cost
                + fixed
            )
            if wait > 0:
                busy += wait
            # No zone bias: lanes from the draft sent champions on long, risky walks.
            score = (late_value if late else early) / (busy * team + capture_time)
            if index == current:
                score *= 1.15
            scored.append((score, index, travel))
            if score > best_score:
                best_score, best_index = score, index
        if best_index is None or cambc.fuel_remaining() < 900_000:
            return best_index

        # Refine the best few with real walking distance, from one search out of our tile.
        scored.sort(reverse=True)
        field = cambc.DistanceField()
        field.compute(k.terrain, nav.tiles_around(position, 0), cambc.Bitboard())
        best = None
        for score, index, estimate in scored[:CANDIDATES]:
            walk = field.get(k.groups[index].anchor)
            if walk >= 65535:
                continue
            score *= (estimate + 10) / (walk + 10)
            if best is None or score > best[0]:
                best = (score, index)
        return best_index if best is None else best[1]

    def farm(self):
        cambc.me()
        k = self.k
        assert k is not None
        now = cambc.round_number()

        # Re-plan every few rounds or when the current target has gone stale.
        if (
            self.target is None
            or k.available[self.target] > now + 25
            or (now % 10 == int(cambc.me()) % 10 and cambc.fuel_remaining() > 1_500_000)
        ):
            self.target = self.choose_target()
        memory.write_claim(self.slot, self.target)
        if self.target is None:
            nav.step_towards(k, k.ally_spawn)
            return "idle"

        info = k.groups[self.target]
        camps = self.target_camps()
        if camps:
            self.engage(camps)
            return "engage"

        # Group in view with no living camps: capture if the reward is up, otherwise move on.
        visible = cambc.vision.visible_tiles()
        in_view = not (info.tiles & visible).is_empty()
        if in_view:
            if k.reward_ready[self.target]:
                self.capture(info)
                return "capture"
            if k.available[self.target] > now:
                self.target = self.choose_target()
                memory.write_claim(self.slot, self.target)
                if self.target is None:
                    return "idle"
                info = k.groups[self.target]
                in_view = not (info.tiles & visible).is_empty()

        # Never wait on spawn tiles: an occupied spawn tile freezes the whole group's respawn.
        # A group due back but still empty is held up by someone on its tiles, quite possibly us.
        position = cambc.me().position()
        if k.available[self.target] > now or (
            in_view and not k.reward_ready[self.target]
        ):
            goals = _ring(info) & ~k.spawn_tiles
            if k.spawn_tiles.is_set(position) or not goals.is_set(position):
                self.travel(goals)
            return "wait"
        self.travel(info.tiles | _ring(info))
        return "travel"

    def travel(self, goals):
        me = cambc.me()
        for ability in me.abilities():
            if (
                ability.is_dash()
                and ability.is_ready()
                and nav.dash_towards(self.k, ability, goals)
            ):
                break
        nav.step_towards(self.k, goals)

    def capture(self, info):
        me = cambc.me()
        k = self.k
        assert k is not None
        position = me.position()

        # An enemy in the region stalls the capture for everyone; fight for it or give it up.
        intruders = [
            enemy
            for enemy in cambc.vision.champions(Team.ENEMY)
            if _alive(enemy) and info.tiles.is_set(enemy.position())
        ]
        if intruders:
            self.contested += 1
            ratio, _ = combat.local_advantage(intruders, radius=8)
            if (
                ratio is not None
                and ratio >= 1.0
                and self.fight_enemies(intruders, aggressive=True)
            ):
                return
            if self.contested > CONTEST_TURNS:
                k.avoid[info.index] = cambc.round_number() + CONTEST_BACKOFF
                self.target = None
                self.contested = 0
                return
        else:
            self.contested = 0

        allies_on = [
            ally
            for ally in cambc.vision.champions(Team.ALLY)
            if ally != me and info.tiles.is_set(ally.position())
        ]
        if info.tiles.is_set(position):
            # Two of us on the region only splits the reward; the higher id leaves.
            if any(int(ally) < int(me) for ally in allies_on):
                k.captured(info.index)
                self.target = None
            return
        if allies_on:
            k.captured(info.index)
            self.target = None
            return
        nav.step_towards(k, info.tiles)

    def engage(self, camps):
        me = cambc.me()
        position = me.position()
        under_fire = any(
            camp.strength() > 0
            and position.chebyshev_distance(camp.position()) <= camp.attack_range()
            for camp in camps
        )
        combat.support_spells(self.k, under_fire)

        # Back off before a camp kills us; it falls asleep two rounds after we leave.
        incoming = sum(
            camp.strength()
            for camp in camps
            if _alive(camp) and camp.health() < camp.max_health()
        )
        if incoming > 0 and me.health() < incoming * 2:
            nav.step_away(self.k, [camp.position() for camp in camps], 4)
            return

        # Never splash a neighbouring armed group awake (01gold-rush's monolith sits beside its gold).
        avoid = self.k.collateral(self.target) if self.target is not None else None
        target = min(
            camps,
            key=lambda camp: (combat.splashes(me, camp, avoid), camp.health()),
        )
        if combat.splashes(me, target, avoid):
            # Every hit we have would splash; leave the rest of this group to someone without splash.
            self.k.avoid[self.target] = cambc.round_number() + CONTEST_BACKOFF
            self.target = None
            return
        if combat.basic_attack(target):
            combat.cast_damage(camps, avoid=avoid)
            return

        cast = combat.cast_damage(camps, avoid=avoid)
        if me.can_move():
            nav.step_towards(
                self.k, nav.tiles_around(target.position(), me.attack_range())
            )
        combat.basic_attack(target)
        if not cast:
            combat.cast_damage(camps, avoid=avoid)


def _ring(info):
    """Tiles next to a group's spawn tiles, so occupied camp tiles still give us somewhere to stand."""
    ring = cambc.Bitboard()
    for position in info.positions:
        ring.draw_chebyshev(position, 1)
    return ring
