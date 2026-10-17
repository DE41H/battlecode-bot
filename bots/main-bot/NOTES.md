# main-bot: working notes and handoff

Context for picking up work on `bots/main-bot` in a fresh session. Read this first, then `GameRules.md` for the rules.

## Where things stand

| What | State |
|---|---|
| `main` / platform submission v7 | v6 with the zone bias removed from target scoring (`nozone`). Locally 306/374 against 11 opponents; 25/34 against v6, 30/34 against the pack-hunting `invader` (v6: 22/34), 28/34 against v5. Practice groups on the platform, same maps and sides as v6's ranked sets: 2/5 against okonomiyaki (v6 2/5), 2/5 against CamboCore (v6 1/5). It still loses the fight-heavy maps badly (`swirl` 38–5 deaths, `eight` 37–13, `contest` 108–7). |
| v6 (`cffdddf`) | On top of v5: tribute abort and unseen-attacker escape, Cassi & Issac retreat at 50% HP (`LINKED_LOW_HEALTH`), camp-damage term cut to 0.25×, ladder-meta draft `Cassi & Issac, Stellar, Ren, Varg, Ryth`. On the ladder it went 18/25 against ranks 279–368, then 9/20 against ranks 260–321; the rank fell from 282 to 324 (rating 1,475). |
| Eval tooling | `tools/eval/`, committed. A 102-game pool takes about a minute (it used to take about 20). |
| Snapshots | `tools/eval/bots/v7` = this submission, `v6`, `v6trip` (runner-up to v6), `invader` (pack-hunting sparring partner, see below). |
| Platform | Team BITSP, id `51e8da36-33a4-4c41-9775-6c463886d003`. Practice-match quota 30 (`cambc match-groups quota --json`). |

The user's git workflow: pull first and resolve conflicts, one-line commit message, **no Claude co-author line**, push to `main` (the `main-bot` branch is kept at the same commit), then `cambc submit main-bot`. Only commit, push or submit when they ask.

## Bot architecture (src/)

- `main.py`: draft vs play dispatch; exceptions are printed and the turn still yields.
- `draft.py`: fixed pick order `Cassi & Issac, Stellar, Ren, Varg, Ryth, ...`; writes angular "zones" (camp group → pick slot) to draft memory.
- `bot.py`: `play_turn` → `decide()` returns a mode label. Order: dead/shop → channel (tribute abort) → heal on spawn → altar lock → unseen-attacker escape → low HP (bank / recall / **last stand** / flee; Cassi & Issac use `LINKED_LOW_HEALTH`) → fight if local power ratio ≥ `FIGHT_EDGE`, retreat if < `RETREAT_EDGE` → snipe → bank → shop recall → `farm()`.
- `farm()` / `choose_target()`: per-champion scoring of every camp group: value / (busy × team + capture), busy = travel + kill + 0.25 × damage-cost + altar + respawn wait, with a current-target bonus (zones no longer count). Claims are shared through 8 bytes of shared memory (byte = slot, value = group + 1). Cassi and Issac share a pick slot, so they share one claim byte and one zone.
- `combat.py`: basic attack plus attack reset, spell selection, Lanchester-style `local_advantage` (Σhealth × Σ(str + 0.25·focus)).
- `knowledge.py`: static group info and per-champion respawn/HP tracking. `nav.py`: DistanceField pathing. `shop.py`: shard build orders.
- `DEBUG = True` in `bot.py` prints one line per champion turn: `round id type x y hp gems gold target #enemies #allies mode`. Printing costs fuel, and the bot branches on `fuel_remaining()`, so traced games drift slightly from untraced ones.

## Game facts learned by experiment (not obvious from the rules)

- **The engine is fully deterministic**, including across `--jobs` counts and `--release`. A mirror match always splits exactly by side. Any code change reshuffles outcomes chaotically, so judge changes on many games (≈170+), never a single map. Even comment-only edits change a few games on fuel-tight maps (`lanes`, `swirl`, `stampede`), because source size changes the first turn's fuel.
- **The top of the ladder is a farming race.** Top teams finish `rows` in about 350 rounds, `lanes` in about 420 and `monolith` in about 410, with 0–4 deaths a game; `contest` is the exception (about 1,500 rounds, dozens of deaths). v6 needs 500–520 (`rows`) and 510–545 (`lanes`) against the starter, so farming speed is still the main gap. Use `cambc matches list` and `cambc matches summary <id> --json -o f.json` to study their games: the stats JSON has per-champion gems, gold, damage and items, plus a submitted-gems timeline.
- **v6's ladder losses were fights, not races.** Grouped opponents (okonomiyaki, rank 279) roam our half and pick off spread-out farmers: on `eight` we died 33 times to their 14 and they took several 132-gem bags; on `swirl` Cassi died seven times at the same contested centre spot, killing Issac each time. On `contest` (monoliths only) v6 died 92–95 times for 0 gems, about half to the monoliths and half to enemies waiting there. `python3 deaths.py summary.json` prints such a death timeline (summary JSON `events`, kind `death`: owner = victim, entry target = killer, x/y, round).
- **Zones were costing us.** The draft's angular lanes gave each champion ×1.3 for its own zone and ×0.85 for others. Removing that (`nozone`) was worth about 26 wins in 204 against v6's pool and, with no other change, lifted the result against the pack-hunting `invader` from 22/34 to 30/34. The zone plan is still computed in `draft.py` and stored in draft memory, but nothing reads it any more.
- **Trickle-feeding is how we lose contested maps.** On `swirl` (practice, v7) the enemy held the centre group all game and lost 5 champions; ours respawned, walked back one at a time and died at the same spot in rotation, so we spent about 63% of the game dead. Avoiding the spot (`deathavoid`, `deathshare`) hands the camp to the enemy and lost more; staging three champions before re-entering (`packdeadly`, `monopack`) did not help either. The fix probably needs real squad play: the whole team picks one objective and arrives together.
- **Pack hunters reproduce the ladder failure locally.** `invader` (v6 + full camp-damage term so the team clumps + double value for camps on the opponent's half) plays like okonomiyaki. As team A on `contest` both v6 and v7 still die about 70 times against it: champions spend almost half the game dead, mostly in `last-stand`/`low-flee` with one ally against two or three enemies.
- **The ladder meta draft** is Cassi & Issac + Stellar in nearly every top team, then Ren, Varg and Ryth (sometimes Tavi). Copying it was worth about 9 wins in 170 on its own and stacked with the farming fix. Draft enum: 0 Ryth, 1 Vesper, 2 Vendetta, 3 C&I, 4 Stellar, 5 Prism, 6 Marcella, 7 Willow, 8 Ren, 9 Varg, 10 Tavi.
- **Where champion turns go** (`profile.sh` vs the starter): `tribfix` waited 27%, engaged 22%, travelled 17%, walked to altars 11%, captured 10%, channelled 5% and was dead 4%. v6 waits 16%, engages 25%, travels 22%, walks to altars 11%, captures 9% and channels 7%.
- **The camp-damage cost was about 9× too high.** The scoring charged strength × kill time of recall trips, but a near-solo wolf-pack clear costs about 300–380 HP, not about 1,600. That made solo targets look terrible, so on `rows` all five champions sat on one group for the whole game while three of them earned no gems or gold at all. 0.25× is the best of 0, 0.15, 0.25, 0.35, 0.5 and 1. **0 is catastrophic** (64/170): the term is what keeps champions off monoliths early.
- **PvP aggression pays.** Lowering the fight threshold from 1.2 to 0.8 was the biggest early gain; making the bot more passive or retreating earlier lost badly.
- **Fleeing at low HP is usually futile.** Chasers keep hitting a champion walking one tile a turn. Fighting back when an enemy is already in range (`last-stand`) was a big gain.
- **Camps do not heal while asleep**, so monolith damage builds up across visits. With late-game items (around round 700) the team kills a 20,000-HP monolith in about 20 rounds.
- **Tributes are a death trap for big bags.** A 200-gem tribute channels for 20 turns, damage does not cancel it, and the killer takes the whole bag. The fix: cancel the tribute when `health <= damage_per_turn * (remaining_channel_time + 1)`; when hit with no visible enemy or camp in range while carrying gems, walk toward spawn and block banking for `AMBUSH_BACKOFF` rounds.
- **Cassi & Issac share a life.** Either one dying kills both and loses both bags. Retreating them at 50% HP helps; dropping them from the draft is much worse.
- **Builds:** top teams buy one emblem per family (Power, Durability, Jungle in the Strength variant, Bruiser Health). Copying that (`bfam`) or taking Jungle-Strength first (`bjs`) lost clearly for us; the +500 HP of Jungle-Health matters.
- **Some maps have no ordinary gems.** On `contest` the only gems are two monoliths; on `stampede`, one 360-gem group of six elks and six gem clusters.
- **Fuel is tight on `lanes`** (about 28k headroom of 2.5M, the map with the most groups).

## Experiment log

Sweep pool (since v6 work) = 17 maps × both sides × {laststand, monoallow, tribfix, goldrush-bot, starter-python} = 170 games. Econ = total rounds to win against the starter over 34 games (lower is faster farming; varies about ±1,000 for unrelated changes). Reference `tribfix`: 115/170, +44.3k, econ 26,416. Win totals vary about ±6 by chance.

| Change | Result | Verdict |
|---|---|---|
| `FIGHT_EDGE` 1.2 → 0.8 | 12/18 vs original (9 maps) | adopted (v5) |
| Last stand when low HP and enemy in range | 60/90 vs older pool, +15.7k gems | adopted (v5) |
| Allow monoliths in target scoring | 63/102 vs ref 61/102; contest 6/6 | adopted (v5) |
| Tribute abort + unseen-attacker escape | 67/102 vs ref 58/102; 22/34 vs v5 | adopted (v6) |
| `cilow`: Cassi & Issac retreat at 50% HP | 122/170, +52.2k, econ 24,975 | adopted (v6) |
| `dmgq`: camp-damage term × 0.25 | 123/170, +43.1k, econ 23,373 | adopted (v6) |
| `dmghalf` × 0.5 / `dmg0` × 0 | 120/170, econ 23,684 / 64/170, −24.4k | 0.5 superseded; 0 rejected |
| `cilow` + × 0.15 / × 0.35 | 114/170 / 108/170 | 0.25 kept |
| `trip125`: heal trip = recall + one walk back | 121/170, +47.8k, econ 24,635 | runner-up (`v6trip`) |
| `dmeta` draft C&I, Stellar, Ren, Varg, Ryth | 124/170, +47.5k | adopted (v6) |
| `dmeta2` (Varg before Ren) / `dstel` / `dren` / `dtavi` | 107 / 113 / 120 / 114 of 170 | rejected |
| v6 = `cilow` + `dmgq` + `dmeta` | 127/170, +55.8k, econ 22,881; 254/374 on 11 opponents | **submitted** |
| `v6trip` = `cilow` + `trip125` + `dmeta` | 125/170, +62.2k; 208/340 on the same 10 others; 21/34 vs v6 | runner-up |
| `zonehalf`: zones only on our half | 109/170 | rejected |
| `ciclaim`: Issac gets his own claim byte | 110/170 | rejected |
| `cap2`: at most two claimants per ordinary group | 106/170 | rejected |
| `share`: allies capture together and split rewards | 105/170 | rejected |
| `bjs` / `bfam` builds | 92/170 / 108/170 | rejected |
| `splash`: Varg and area spells aim at the pack centre | 115/170, neutral | not adopted |
| **v7 work** (pool: v6 mirror, v6trip, monoallow, tribfix, goldrush, starter = 204; v6 = 138/204, +49.7k) | | |
| `nozone`: no zone bias in target scoring | 164/204, +72.9k, econ 22,265; 25/34 vs v6 | **adopted (v7)** |
| `linkfocus` (focus Cassi/Issac: half health) / `dangerbank` (bank 30+ gems within 40 rounds of seeing enemies) | 142 / 140 of 204 | neutral |
| `bank40` / `bank100` / `shop90` / `waitpen` / `interrupt` / `deathavoid` (avoid where we died, 120 rounds) | 141 / 142 / 137 / 142 / 139 / 136 of 204 | neutral |
| `retreatall` (retreat when odds < 0.5 even with an empty bag) | 136/204 | neutral |
| `regroup` (retreat toward the nearest ally) / `dangerzone` (shared enemy-group sightings; avoid those camps) | 133 / 126 of 204 | rejected |
| `rally` (shared help call) / `fight10` (`FIGHT_EDGE` 1.0) | 119 / 122 of 204 | rejected |
| On v7 (pool adds `invader`, v7 mirror = 238; v7 = 185/238, +76.3k): `bank100`, `waitpen`, `linkfocus`, `deathavoid`, `f07`, `adaptive` (pack up for 60 rounds after any ally sees an enemy group), `trip125` | 186, 185, 180, 183, 181, 176, 172 of 238 | none better than v7 |
| On v7, cont.: `dangerbank`, `bankdist` (bank once gems ≥ 20 + 4 × altar distance), `nostick`, `stick13`, `cand5` | 183, 186, 173, 174, 179 of 238 | none better than v7 |
| `deathshare`: shared "ally killed here" marker; everyone avoids that group for 80 rounds | 5/12 vs `invader` on contest, swirl, eight, ambush, monolith, corners (v7: 10/12) | rejected |
| `packdeadly`: same marker, but gather three champions before re-entering instead of avoiding | 7/12 on the same games | rejected |
| `monopack`: gather three champions before engaging a monolith | contest slower vs the starter (1,816–2,000 vs 1,137–1,267 rounds); no change vs `invader` | rejected |
| `noci`: drop Cassi & Issac from draft | 47/102, −7.8k | rejected |
| `waitpen`: 1.5× respawn-wait penalty | 62/102 (old pool), neutral | retest on v6 |
| `safebank`, `interrupt`, herd leadership, `LOW_HEALTH` 0.5 | all lost | rejected |
| Never tested on v6 | `waitpen`, `shop90`, `bank40`, `bank100`, `nozone`, `f06`, `r05`, `rally`, `interrupt` | patches exist |

## Eval harness (`tools/eval/`)

Run everything from `tools/eval/`. Output goes to `tools/eval/work/` (gitignored). The opponent snapshots in `bots/` are source only.

Why it is fast: a match itself costs about 1 s of CPU, but every `cambc run` rebuilds both bots (about 18 s CPU each) and JIT-compiles their 41 MB wasm modules (about 20 s CPU each). `evalbots.py` puts every game into one `cambc run-batch` (each bot built once) and sets `CAMBC_WASMTIME_CACHE=work/wtcache` so compiled modules are reused across matches and runs. It also copies each bot's `src/` into its own staging dir, so concurrent runs never race on a build dir and edits can never run stale builds.

- `bots/`: `baseline` (original commit 738d4b1), `aggro` (+fight 0.8), `f08r07`, `laststand`, `monoallow` (= v5), `tribfix` (v5 + tribute fix), `v6`, `v6trip`, `v7`, `invader` (pack-hunting sparring partner; `patches/invader.py` on v6).
- `python3 scrim.py TEAM_ID m1,m2,m3,m4,m5`: queue a five-match practice group on the platform (spends shared quota; plays our *current submission*), wait and report per map. `--group ID` reports an existing group. Team ids: `cambc ladder --page N`, or every team's rank in `cambc match-groups quota --json` (`opponentRanks`). Our own matches: `cambc matches list --team <our id>`; each one's stats: `cambc matches summary <id> --json -o f.json`.
- `evalbots.py X OPP [OPP...] [--maps a,b] [--jobs N] [--keep] [--debug-mode]`: X against every opponent on every map, both sides, in one batch (release mode, like the platform). Prints `RES map side won gx gy round kx ky opp` lines, per-opponent summaries and a `TOTAL` line; appends every game to `work/results.jsonl`.
- `./sweep.sh VARIANT...` (env `OPPS`, default `v7 v6 v6trip invader monoallow goldrush-bot starter-python`): evaluates each `bots/VARIANT` in turn; about 3 minutes per variant. `python3 summary.py [--opps a,b] [variant...]` tabulates the latest run of each variant, with econ from the starter games. Reference: **v7 185/238, +76.3k, econ 22,265** (mirror 17/34; 25/34 v6, 22/34 v6trip, 30/34 invader, 28/34 monoallow, 29/34 goldrush, 34/34 starter).
- `./mkpatch.sh NAME patch1 patch2 ...`: copies `bots/main-bot` to `tools/eval/bots/NAME` and applies `patches/*.py`. Most patches were written against `tribfix`; use `BASE=bots/tribfix` for those whose lines v6 changed (the damage-factor, draft and `cilow` patches already apply or conflict).
- `./pool.sh bots/NAME [opps...]` (default `v7 v6 v6trip invader monoallow goldrush-bot`) and `./econ.sh bots/NAME` (against the starter only) are thin wrappers around `evalbots.py`.
- `./profile.sh VARIANT [OPP]`: traced games on every map; prints the share of champion turns per mode (`BYTYPE=1` adds a per-champion-type breakdown).
- `./trace.sh MAP [OPP]`: one traced game of the current main-bot with camp HP lines (`H round id [(group, hp)...]`); the trace is in `work/runs/tr-MAP/a.txt`. Opponents resolve from `tools/eval/bots/` or the repo's `bots/`.
- `patches/groupdump.py`: probe that prints every group (index, centre, gems, gold, respawn, HP, strength, zone) and each re-plan's top scores.

Gotchas:

- Never `pkill -f` or `pgrep -f` a pattern that appears in your own shell command; it matches the calling shell (a `while pgrep -f ...` loop never ends). Wait on a PID with `kill -0` instead.
- `cambc run-batch` refuses to overwrite existing replay paths; manifest paths are resolved relative to the manifest, so use absolute paths.
- Bot stdout is in the replay zip (`team-a.stdout`). It contains control characters, so clean it with `tr -cd '\11\12\40-\176'`.

## Suggested next steps

0. Watch v7 on the ladder (`cambc matches list --team 51e8da36-33a4-4c41-9775-6c463886d003`) and use practice groups (`scrim.py`) against teams that beat v6: okonomiyaki `5cc17226-5367-4168-90c5-0ac7affe1f5f`, CamboCore `15635837-d5c9-4f7e-8f9e-59fe7530dc13`, Hide on Bush `76f2d18c-ffb5-4d34-b29c-30c552bb3420`.
1. Grouped play against pack hunters, above all on `contest`: our spread-out champions lose every 1-v-3. Ideas not yet built: move as one pack only on monolith-only maps, or only after an enemy pack has been seen on our half. `adaptive` (clump for 60 rounds after any sighting) and `monopack` were not enough.
2. Farming is still about 1.4× slower than the top teams. Attack the biggest non-engage buckets in the v6 profile: travel (22%), waiting for respawns (16%), walking to altars (bank when passing an altar, or during a respawn wait, rather than on a fixed 60-gem threshold), and capture overhead.
3. Still untested on v7: `f06`, `r05`, `splash`, `bankdist`, `nostick`/`stick13`/`cand5` (`BASE=../../bots/main-bot ./mkpatch.sh NAME PATCH`).
4. Understand why `v6trip` beats v6 head to head while losing on the wider pool; a mix of `trip125` and a factor between 0.25 and 0.5 may be better than either.
5. Kill speed: `splash` was neutral on its own; combined with faster target rotation it may pay off.
6. Monolith timing on `contest`: commit earlier and escort the carrier; v6 finishes it in 1,140–1,270 rounds against the starter (v5: 1,550–1,650).
