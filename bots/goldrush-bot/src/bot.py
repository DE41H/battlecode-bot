"""Champion decisions — goldrush-bot (Tavi Economy strategy).

Champions share a role decoded from draft memory:

  ROLE_ANCHOR  (Tavi)        — never recalls; banks at 30 gems; writes Tavi-anchor byte
  ROLE_SUPPORT (Willow)      — stays near Tavi; heals before farming; banks at 50 gems
  ROLE_ECON    (Vesper Vale) — recalls at 120g to compound gold; banks at 45 gems
  ROLE_FIGHTER (everyone else) — standard 60-gem banking; responds to monolith signal

Shared memory is read/written every turn to coordinate banking, gem load,
Tavi position and monolith availability.  See memory.py for layout details.

Fixes applied vs initial version:
  1  knowledge.py: late_value for gold camps → 0.05*gold (Vale stays active post-700)
  2  knowledge.py: extended scoring tuple with raw gold/gems; correct gold-fraction formula
  3  Willow heal filter: any missing HP, not >= heal_amount (was blocking heals on Tavi)
  4  Distress signal wired: fighters route to hurt visible allies when distress set
  5  Tavi bank-altar range: 12 → 5; guard uses threats not enemies
  6  knowledge.py: monolith alive clears the signal (not just on capture)
  7  Banking flag cleared immediately after submit_gems succeeds
  8  Retreat uses dashes before step_away
  9  Ward placement: place once per game on a strategic tile
 10  Double-fight-call: confirmed already guarded by return; no change needed
 11  Tavi trip_cost zeroed in scoring (no recall penalty)
 12  Varg targets highest-HP center camp for splash coverage
 13  _least_congested_altar: removed dead read_banking_flags() call
 14  Shop recall threshold: 150 → 120 (4 shards boundary, less gold stranded)
 15  Champion priorities set in setup (Tavi=10, Willow=5, others=0)
"""

import math

import cambc
import combat
import memory
import nav
from knowledge import Knowledge
from shop import shop

Team, Kind, Consumable = cambc.Team, cambc.ChampionType, cambc.ConsumableType

LOW_HEALTH   = 0.35
HEALED       = 0.90
FIGHT_EDGE   = 1.20
RETREAT_EDGE = 0.90
CONTEST_TURNS   = 4
CONTEST_BACKOFF = 30
# Fix 14: was 150 (exact emblem), 149g would strand indefinitely; 120 = 4-shard boundary.
SHOP_GOLD_DEFAULT = 120
SHOP_GOLD_VALE    = 80
# Fix 5: was 12 (too risky at 35% HP over that range). 5 tiles is safely reachable.
TAVI_BANK_ALTAR_RANGE = 5
CANDIDATES = 3
# Willow proximity: bias zone score toward camps within this Chebyshev distance of Tavi.
WILLOW_PROXIMITY_RADIUS = 10
WILLOW_PROXIMITY_BONUS  = 0.40
# Monolith: fighters boost Monolith score when memory says it's available.
MONOLITH_BOOST = 2.5
# Priorities: higher value acts first in a round.
PRIORITY_TAVI   = 10

# B2: role-based bank thresholds used when draft memory is absent.
# Mirrors _BANK_GEMS in draft.py so the fallback matches the intended design.
_ROLE_THRESHOLDS = {
    memory.ROLE_ANCHOR:  30,
    memory.ROLE_SUPPORT: 50,
    memory.ROLE_ECON:    45,
    memory.ROLE_FIGHTER: 40,
}
PRIORITY_WILLOW = 5
PRIORITY_DEFAULT = 0
DEBUG = False


def _alive(unit):
    try:
        return unit.is_visible() and unit.health() > 0
    except cambc.Error:
        return False


class Bot:
    def __init__(self):
        self.k:    Knowledge | None = None
        self.plan: memory.Plan | None = None
        self.slot: int | None = None
        self.role: int        = memory.ROLE_FIGHTER
        self.target:    int | None = None
        self.healing:   bool       = False
        self.contested: int        = 0
        self._ward_placed: bool    = False  # Fix 9

    # ── setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        me         = cambc.me()
        self.k     = Knowledge()
        self.plan  = memory.Plan()
        self.slot  = self.plan.slot_of(me.champion_name())
        if self.slot is None:
            self.slot = int(me) % memory.CLAIM_SLOTS
        self.role = self.plan.role_of(self.slot)

        # B1: fallback role detection from champion name.
        # When draft_memory.submit fails (encode_plan exception), Plan is empty
        # and role_of returns ROLE_FIGHTER for everyone.  Correct it so Tavi
        # shops in-field and Vale uses the gold-zone recall threshold, even
        # without a valid plan in memory.
        if self.role == memory.ROLE_FIGHTER:
            _ct = me.champion_name()
            if _ct == cambc.ChampionType.TAVI:
                self.role = memory.ROLE_ANCHOR
            elif _ct == cambc.ChampionType.WILLOW:
                self.role = memory.ROLE_SUPPORT
            elif _ct == cambc.ChampionType.VESPER_VALE:
                self.role = memory.ROLE_ECON

        # Higher priority acts first; Tavi banks before enemies can intercept.
        if self.is_tavi:
            me.set_priority(PRIORITY_TAVI)
        elif self.is_willow:
            me.set_priority(PRIORITY_WILLOW)
        else:
            me.set_priority(PRIORITY_DEFAULT)

    @property
    def is_tavi(self):
        return self.role == memory.ROLE_ANCHOR

    @property
    def is_willow(self):
        return self.role == memory.ROLE_SUPPORT

    @property
    def is_vale(self):
        return self.role == memory.ROLE_ECON

    @property
    def bank_threshold(self):
        # B2: use plan value when available; fall back to role-based default
        # so Tavi gets 30-gem threshold even when draft memory is empty.
        if self.plan is not None:
            t = self.plan.bank_threshold(self.slot)
            if t > 0:
                return t
        return _ROLE_THRESHOLDS.get(self.role, 40)

    @property
    def shop_gold_threshold(self):
        return SHOP_GOLD_VALE if self.is_vale else SHOP_GOLD_DEFAULT

    @property
    def has_support(self):
        """True when Willow was actually drafted — Tavi can rely on in-field healing."""
        return self.plan is not None and self.plan.willow_slot is not None

    # ── turn ──────────────────────────────────────────────────────────────────

    def play_turn(self):
        me = cambc.me()
        if self.k is None:
            self.setup()
        k = self.k
        assert k is not None
        k.observe()

        # Dead: shop, clear claim + flags, wait for respawn.
        if not me.is_alive():
            self.healing = False
            self.target  = None
            memory.write_claim(self.slot, None)
            memory.write_banking(self.slot, False)
            memory.write_heavy_gems(self.slot, False)
            if self.is_tavi:
                memory.write_tavi_group(None)
            shop()
            return

        # Let ongoing channels run.
        if me.is_submitting_gems() or me.is_recalling() or me.is_teleporting():
            return

        position = me.position()
        at_spawn = k.ally_spawn.is_set(position)

        # Shop: Tavi can shop anywhere; others shop only on spawn.
        if at_spawn or self.is_tavi:
            shop()

        # After a recall, wait on spawn until healed.
        if at_spawn and self.healing and me.health() < me.max_health() * HEALED:
            return
        self.healing = False

        enemies = [e for e in cambc.vision.champions(Team.ENEMY) if _alive(e)]
        hostile_camps = [
            c for c in cambc.vision.camps()
            if _alive(c) and c.strength() > 0 and c.health() < c.max_health()
        ]

        # Fix 9: place ward on first useful opportunity.
        if not self._ward_placed and not at_spawn:
            self._try_place_ward()

        # Altar lock: cancel an enemy tribute.
        self.place_altar_lock(enemies)

        # ── Willow: heal a hurt ally before doing anything else ───────────────
        if self.is_willow:
            if self._willow_heal():
                return

        # ── Low health handling ───────────────────────────────────────────────
        if not at_spawn and me.health() < me.max_health() * LOW_HEALTH:
            threats = [
                e.position() for e in enemies
                if position.chebyshev_distance(e.position()) <= 6
            ] + [
                c.position() for c in hostile_camps
                if position.chebyshev_distance(c.position()) <= 4
            ]

            # Tavi-specific: bank or step away rather than recall.
            if self.is_tavi:
                self._tavi_low_hp(threats, enemies)
                return

            # Standard: bank if sitting next to altar, otherwise recall or step away.
            if (
                me.gem_count() > 0
                and k.nearest_altar_distance(position) <= 2
                and not enemies
            ):
                self.bank()
                return
            if not threats:
                me.recall()
                self.healing = True
                return
            # Fix 8: try dashing to safety before step_away.
            self._dash_away(threats)
            nav.step_away(k, threats, 4)
            return

        # ── PvP ───────────────────────────────────────────────────────────────
        ratio, near = combat.local_advantage(enemies)
        if ratio is not None:
            if ratio >= FIGHT_EDGE and self.fight_enemies(near, aggressive=True):
                return
            if ratio < RETREAT_EDGE and (
                me.gem_count() > 0 or me.health() < me.max_health() * 0.6
            ):
                memory.write_distress(self.slot, True)
                # Fix 8: dash away before step_away in retreat.
                self._dash_away([e.position() for e in near])
                nav.step_away(k, [e.position() for e in near], 6)
                return
        memory.write_distress(self.slot, False)
        if self.fight_enemies(enemies):
            return

        # ── Banking ───────────────────────────────────────────────────────────
        if self.should_bank(enemies):
            memory.write_banking(self.slot, True)
            memory.write_heavy_gems(self.slot, me.gem_count() >= 30)
            self.bank()
            return
        memory.write_banking(self.slot, False)
        memory.write_heavy_gems(self.slot, me.gem_count() >= 30)

        # ── Recall to shop ────────────────────────────────────────────────────
        # B5: don't burn 5-turn recall channel when enemy is close to winning.
        _enemy_near_win = (
            cambc.global_submitted_gems(Team.ENEMY) + 100 >= cambc.constants.WINNING_GEMS
        )
        if (
            not _enemy_near_win
            and not at_spawn
            and not self.is_tavi                   # Tavi shops in-field
            and me.gem_count() <= (10 if self.is_vale else 0)  # B4: Vale recalls with ≤10 gems
            and me.gold_count() >= self.shop_gold_threshold
            and not hostile_camps
            and not enemies
            and self.target_camps() == []
        ):
            me.recall()
            self.healing = True
            return

        if DEBUG and cambc.round_number() % 20 == 0:
            print(
                cambc.round_number(), int(me.champion_name()),
                me.position(), "hp", int(me.health()),
                "gems", me.gem_count(), "gold", me.gold_count(),
                "role", self.role, "target", self.target,
                "claims", memory.read_claims(),
            )

        self.farm()

    # ── Tavi-specific low-HP logic ────────────────────────────────────────────

    def _tavi_low_hp(self, threats, enemies):
        """Tavi low-HP routing.

        When Willow is drafted (has_support=True): avoid recall, bank or step
        toward spawn for an in-field heal.
        When Willow is NOT drafted (Fix 4): fall back to standard recall so
        Tavi isn't stuck field-farming at 30% HP with no healer.
        """
        me       = cambc.me()
        k        = self.k
        assert k is not None
        position = me.position()

        # Fix 4: without Willow, Tavi gains nothing by staying in field at low HP.
        # Use standard recall/flee behavior identical to other champions.
        if not self.has_support:
            if me.gem_count() > 0 and k.nearest_altar_distance(position) <= 2 and not enemies:
                self.bank()
                return
            if not threats:
                me.recall()
                self.healing = True
                return
            self._dash_away(threats)
            nav.step_away(k, threats, 4)
            return

        # Willow is on the team — try to stay in field.
        # Fix 5: was 12 (too dangerous); now 5. Check threats not enemies so a
        # distant enemy farming elsewhere doesn't block banking.
        if (
            me.gem_count() > 0
            and k.nearest_altar_distance(position) <= TAVI_BANK_ALTAR_RANGE
            and not threats
        ):
            self.bank()
            return

        # No threats: head toward spawn so Willow can heal us.
        if not threats:
            nav.step_towards(k, k.ally_spawn)
            return

        # Threats present: run (dash first).
        self._dash_away(threats)
        nav.step_away(k, threats, 4)

        # True last resort: recall only if we have no gems and cannot escape.
        if me.gem_count() == 0 and threats:
            me.recall()
            self.healing = True

    # ── dash-away helper (Fix 8) ──────────────────────────────────────────────

    def _dash_away(self, threat_positions):
        """Try to use a dash ability to maximise distance from threat_positions."""
        if not threat_positions:
            return
        me     = cambc.me()
        origin = me.position()
        for ability in me.abilities():
            if not ability.is_dash() or not ability.is_ready():
                continue
            blocked = nav.blocked_tiles(self.k)
            landing = nav.tiles_around(origin, 2) & ~blocked

            def _safety(tile):
                return min(tile.chebyshev_distance(t) for t in threat_positions)

            best = max(landing.positions(), key=_safety, default=None)
            if best and _safety(best) > _safety(origin):
                try:
                    ability.use(best)
                except cambc.Error:
                    pass
            break  # one dash max

    # ── ward placement (Fix 9) ────────────────────────────────────────────────

    def _try_place_ward(self):
        """Place ward on a strategic tile near current position. Runs until placed."""
        me = cambc.me()
        if me.ward_cooldown() > 0:
            return
        k = self.k
        assert k is not None
        placement = me.ward_placement_tiles()
        if placement.is_empty():
            return

        position = me.position()

        # Prefer: tile covering the monolith, then our current target camp,
        # then just wherever we are (still provides vision of this area).
        def _score(tile):
            s = 0
            for info in k.groups:
                if info.has_monolith and tile.chebyshev_distance(info.center) <= 6:
                    s += 100
                    break
            if self.target is not None and self.target < len(k.groups):
                tg = k.groups[self.target]
                if tile.chebyshev_distance(tg.center) <= 6:
                    s += 20
            return s

        best = max(placement.positions(), key=_score, default=None)
        if best is None:
            return
        try:
            if me.place_ward(best):
                self._ward_placed = True
        except cambc.Error:
            pass

    # ── Willow heal ───────────────────────────────────────────────────────────

    def _willow_heal(self):
        """Try to heal the most-hurt ally in range; return True if we spent the ability."""
        me = cambc.me()
        for ability in me.abilities():
            if not ability.is_heal() or not ability.is_ready():
                continue
            try:
                # Fix 3: was checking `missing >= heal_amount` which excluded allies
                # missing less than the raw heal value (e.g. Tavi missing 300, heal=315).
                # Now: any ally with missing HP qualifies; game caps the heal automatically.
                reach = int(getattr(ability.info(), "range", 4))
                hurt  = [
                    ally for ally in cambc.vision.champions(Team.ALLY)
                    if ally != me
                    and _alive(ally)
                    and me.position().chebyshev_distance(ally.position()) <= reach
                    and ally.health() < ally.max_health()
                ]
                if hurt:
                    target = min(hurt, key=lambda a: a.health() / a.max_health())
                    return ability.use(target)
            except cambc.Error:
                continue
        return False

    # ── banking ───────────────────────────────────────────────────────────────

    def usable_altars(self):
        k = self.k
        assert k is not None
        altars = []
        for altar in k.altars:
            try:
                if (
                    cambc.vision.has_altar_lock(altar)
                    and cambc.vision.altar_lock_at(altar).is_enemy()
                ):
                    continue
            except cambc.Error:
                pass
            altars.append(altar)
        return altars or k.altars

    def _nearest_altar(self, altars):
        # Fix 13: removed dead read_banking_flags() + read_claims() calls.
        # ponytail: closest altar wins; split-team load balancing isn't worth the complexity.
        if not altars:
            return None
        if len(altars) == 1:
            return altars[0]
        position = cambc.me().position()
        return min(altars, key=lambda a: position.chebyshev_distance(a))

    def should_bank(self, enemies):
        me    = cambc.me()
        gems  = me.gem_count()
        if gems <= 0:
            return False
        k = self.k
        assert k is not None
        position      = me.position()
        altar_dist    = k.nearest_altar_distance(position)
        rounds_left   = cambc.constants.MAX_ROUNDS - cambc.round_number()
        threshold     = self.bank_threshold

        # B3: urgency — if enemy is within 80 gems of winning, bank now.
        # 80 covers roughly one full champion load and prevents losing the
        # gem race because we were carrying gems at the wrong moment.
        if cambc.global_submitted_gems(Team.ENEMY) + 80 >= cambc.constants.WINNING_GEMS:
            return True

        if rounds_left < altar_dist * 1.4 + math.ceil(gems / 10) + 15:
            return True
        if cambc.global_submitted_gems(Team.ALLY) + gems >= cambc.constants.WINNING_GEMS:
            return True
        if gems >= threshold:
            return True
        if altar_dist <= 5 and not self.target_camps():
            return True
        if self.target is not None:
            waiting = k.available[self.target] - cambc.round_number()
            if waiting > 0 and waiting >= altar_dist:
                return True
        if gems >= 10 and enemies:
            return True
        return me.health() < me.max_health() * 0.5

    def bank(self):
        me       = cambc.me()
        position = me.position()
        reach    = cambc.constants.SUBMIT_GEMS_RANGE
        altars   = self.usable_altars()
        best     = self._nearest_altar(altars)
        if best is None:
            return

        if position.chebyshev_distance(best) <= reach:
            try:
                # Fix 7: clear banking flag immediately after successful submit
                # so teammates don't see a stale True on the next turn.
                if me.submit_gems(best):
                    memory.write_banking(self.slot, False)
                return
            except cambc.Error:
                pass

        goals = cambc.Bitboard()
        for altar in altars:
            goals |= nav.tiles_around(altar, reach)
        nav.step_towards(self.k, goals)

    # ── PvP ───────────────────────────────────────────────────────────────────

    def fight_enemies(self, enemies, aggressive=False):
        """Kill shots, gem robbery, or full aggression when we have the edge."""
        me       = cambc.me()
        if not enemies:
            return False
        position = me.position()
        burst    = combat.burst_estimate(me)
        worth    = []
        for enemy in enemies:
            try:
                gems = enemy.gem_count()
            except cambc.Error:
                gems = 0
            in_reach = position.chebyshev_distance(enemy.position()) <= max(me.attack_range(), 4)
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

        def _priority(e):
            try:
                gems = e.gem_count()
            except cambc.Error:
                gems = 0
            return (-gems, e.health())

        target = min(worth, key=_priority)
        acted  = combat.cast_damage([target])
        acted  = combat.basic_attack(target) or acted
        if not acted and me.can_move():
            acted = nav.step_towards(
                self.k, nav.tiles_around(target.position(), me.attack_range())
            )
            combat.basic_attack(target)
        return acted

    def place_altar_lock(self, enemies):
        me = cambc.me()
        try:
            lock = me.consumables()[int(Consumable.ALTAR_LOCK)]
            if lock.count() <= 0:
                return False
        except cambc.Error:
            return False
        k        = self.k
        assert k is not None
        position = me.position()
        for enemy in enemies:
            try:
                if not enemy.is_submitting_gems():
                    continue
            except cambc.Error:
                continue
            for altar in k.altars:
                if altar.chebyshev_distance(enemy.position()) > cambc.constants.SUBMIT_GEMS_RANGE:
                    continue
                if position.chebyshev_distance(altar) > 2 or cambc.vision.has_altar_lock(altar):
                    continue
                try:
                    if lock.use(altar):
                        return True
                except cambc.Error:
                    continue
        return False

    # ── farming ───────────────────────────────────────────────────────────────

    def target_camps(self):
        if self.target is None:
            return []
        return [
            c for c in cambc.vision.camps()
            if int(c.camp_group()) == self.target and _alive(c)
        ]

    def choose_target(self):
        me    = cambc.me()
        k     = self.k
        assert k is not None and self.plan is not None
        now      = cambc.round_number()
        position = me.position()
        px, py   = position.x, position.y
        dps      = combat.sustained_damage(me)
        budget   = me.max_health() * (1 - LOW_HEALTH)

        others_on = {}
        for slot, claim in enumerate(memory.read_claims()):
            if claim is not None and slot != self.slot:
                others_on[claim] = others_on.get(claim, 0) + 1

        # Willow: find Tavi's group centre for proximity bias.
        tavi_group_idx = memory.read_tavi_group() if self.is_willow else None
        tavi_cx = tavi_cy = None
        if tavi_group_idx is not None and tavi_group_idx < len(k.groups):
            tavi_info = k.groups[tavi_group_idx]
            tavi_cx, tavi_cy = tavi_info.cx, tavi_info.cy

        # Fighters: check if monolith is available (memory signal).
        monolith_available = (
            not self.is_tavi and not self.is_willow and memory.read_monolith_down()
        )

        late                        = now >= 700
        available, remaining, avoid = k.available, k.remaining, k.avoid
        capture_time                = k.capture_time
        my_zone, current            = self.slot, self.target

        best_score, best_index, scored = -1.0, None, []

        # Check monolith groups first if the signal is set.
        if monolith_available:
            for info in k.monolith_groups():
                if avoid[info.index] > now:
                    continue
                travel = max(abs(info.cx - px), abs(info.cy - py)) * 1.25
                team   = 1 + others_on.get(info.index, 0)
                score  = MONOLITH_BOOST * info.gems / (travel + capture_time + 1)
                if score > best_score:
                    best_score, best_index = score, info.index
                scored.append((score, info.index, travel))

        # Fix 2: extended tuple now has raw gold/gems at indices 10/11.
        for (
            index, cx, cy, early, late_value,
            trip_cost, fixed, strength, zone, prio_mult,
            info_gold, info_gems,
        ) in k.scoring:
            if late and late_value <= 0:
                continue
            team   = 1 + others_on.get(index, 0)
            kill   = remaining[index] / (dps * team)
            travel = max(abs(cx - px), abs(cy - py)) * 1.25
            wait   = max(available[index], avoid[index]) - now - travel

            # Fix 11: Tavi never recalls, so trip_cost (which encodes recall time) should
            # not penalise Tavi for farming distant camps.
            effective_trip = 0.0 if self.is_tavi else trip_cost

            busy  = travel + kill + strength * kill / team / budget * effective_trip + fixed
            if wait > 0:
                busy += wait
            score = (late_value if late else early) / (busy * team + capture_time)

            score *= prio_mult

            # Zone affinity.
            if zone == my_zone:
                score *= 1.3
            elif zone >= 0:
                score *= 0.85

            # Sticky bonus for current target.
            if index == current:
                score *= 1.15

            # Willow proximity bias: favour camps near Tavi.
            if self.is_willow and tavi_cx is not None:
                dist_to_tavi = max(abs(cx - tavi_cx), abs(cy - tavi_cy))
                if dist_to_tavi <= WILLOW_PROXIMITY_RADIUS:
                    score *= (1.0 + WILLOW_PROXIMITY_BONUS)

            # Fix 2: correct gold-fraction using raw values from the tuple.
            if self.is_vale:
                gold_frac = info_gold / (info_gems + info_gold + 1)
                score *= (1.0 + 0.3 * gold_frac)

            scored.append((score, index, travel))
            if score > best_score:
                best_score, best_index = score, index

        if best_index is None or cambc.fuel_remaining() < 900_000:
            return best_index

        # Refine top candidates with real walking distance.
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
        k   = self.k
        assert k is not None
        me  = cambc.me()
        now = cambc.round_number()

        # Fix 4: if distress signal is set and we're a fighter with no gem load,
        # route toward any visible hurt ally to provide numerical support.
        if (
            not self.is_tavi
            and not self.is_willow
            and memory.read_distress()
        ):
            position = me.position()
            hurt = [
                a for a in cambc.vision.champions(Team.ALLY)
                if a != me and _alive(a) and a.health() < a.max_health() * 0.40
            ]
            if hurt:
                nearest = min(hurt, key=lambda a: position.chebyshev_distance(a.position()))
                nav.step_towards(k, nav.tiles_around(nearest.position(), 3))
                return

        if (
            self.target is None
            or k.available[self.target] > now + 25
            or (now % 10 == int(me) % 10 and cambc.fuel_remaining() > 1_500_000)
        ):
            self.target = self.choose_target()

        memory.write_claim(self.slot, self.target)
        if self.is_tavi:
            memory.write_tavi_group(self.target)

        if self.target is None:
            nav.step_towards(k, k.ally_spawn)
            return

        info  = k.groups[self.target]
        camps = self.target_camps()
        if camps:
            self.engage(camps)
            return

        visible = cambc.vision.visible_tiles()
        if not (info.tiles & visible).is_empty():
            if k.reward_ready[self.target]:
                self.capture(info)
                return
            if k.available[self.target] > now:
                self.target = self.choose_target()
                memory.write_claim(self.slot, self.target)
                if self.is_tavi:
                    memory.write_tavi_group(self.target)
                if self.target is None:
                    return
                info = k.groups[self.target]

        position = me.position()
        if k.available[self.target] > now:
            goals = _ring(info) & ~info.tiles
            if info.tiles.is_set(position) or not goals.is_set(position):
                self.travel(goals)
            return
        self.travel(info.tiles | _ring(info))

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
        me       = cambc.me()
        k        = self.k
        assert k is not None
        position = me.position()

        intruders = [
            e for e in cambc.vision.champions(Team.ENEMY)
            if _alive(e) and info.tiles.is_set(e.position())
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
                self.target    = None
                self.contested = 0
                return
        else:
            self.contested = 0

        allies_on = [
            a for a in cambc.vision.champions(Team.ALLY)
            if a != me and info.tiles.is_set(a.position())
        ]
        if info.tiles.is_set(position):
            if any(int(a) < int(me) for a in allies_on):
                k.captured(info.index)
                self.target = None
            return
        if allies_on:
            k.captured(info.index)
            self.target = None
            return
        nav.step_towards(k, info.tiles)

    def engage(self, camps):
        me       = cambc.me()
        position = me.position()
        under_fire = any(
            c.strength() > 0
            and position.chebyshev_distance(c.position()) <= c.attack_range()
            for c in camps
        )
        combat.support_spells(self.k, under_fire)

        incoming = sum(
            c.strength() for c in camps
            if _alive(c) and c.health() < c.max_health()
        )
        if incoming > 0 and me.health() < incoming * 2:
            nav.step_away(self.k, [c.position() for c in camps], 4)
            return

        # Fix 12: Varg's splash hits all camps within radius 1 of target.
        # Attack the highest-HP camp near the cluster center for max AoE.
        is_varg = (me.champion_name() == cambc.ChampionType.VARG)
        if is_varg and len(camps) > 1:
            # ponytail: Chebyshev center approximation; picks camp closest to group centroid
            cx = sum(c.position().x for c in camps) // len(camps)
            cy = sum(c.position().y for c in camps) // len(camps)
            center_pos = cambc.Vec2(cx, cy)
            central = min(camps, key=lambda c: center_pos.chebyshev_distance(c.position()))
            target = max(
                [c for c in camps if center_pos.chebyshev_distance(c.position()) <= 1],
                key=lambda c: c.health(),
                default=central,
            )
        else:
            target = min(camps, key=lambda c: c.health())

        if combat.basic_attack(target):
            combat.cast_damage(camps)
            return
        cast = combat.cast_damage(camps)
        if me.can_move():
            nav.step_towards(self.k, nav.tiles_around(target.position(), me.attack_range()))
        combat.basic_attack(target)
        if not cast:
            combat.cast_damage(camps)


def _ring(info):
    ring = cambc.Bitboard()
    for position in info.positions:
        ring.draw_chebyshev(position, 1)
    return ring
