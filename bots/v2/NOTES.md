# v2: tank builds + wards (working notes)

v2 is `bots/v1` (submission v8) plus two changes copied from the ladder. Everything in `bots/v1/NOTES.md` (architecture, harness, game facts) still applies. Not submitted yet.

## Why

Ladder study (2026-10-20, engine 1.0.0): 180 ranked games between top-15 teams, plus 30 games of Mommy Shogun (rank 71, 36/50 ranked), who beat v8 4–1 in scrims with the same draft as ours.

- We died a median of **33 times a game** against Mommy Shogun; they died 6 (79 times on `01hooks`, almost all to champions, in the same 10×10 area all game).
- **We never placed a ward.** Top teams place 75–450 a game; Mommy Shogun about 444. Vision is not shared, so a ward is a lone farmer's only early warning.
- **Builds:** top-15 emblem families are Durability > Power > Bruiser > Jungle, with Monster rare. We bought Monster + Power + Jungle and no Durability. Mommy Shogun: Jungle first, then Durability, then repeated Bruiser emblems.
- Winners vs losers (top-15 games): deaths 8 vs 16, kills 9 vs 3, tributes 34 vs 16.

## What changed

- `shop.py`: Mommy Shogun's build per champion. Melee: Jungle-Health → Durability-Strength → Bruiser-Health (Issac adds Monster-Strength), then Bruiser. Varg: Jungle-Strength → Durability-Health → Bruiser. Casters: Bruiser-Focus ×2 → Bruiser-Health → Bruiser-Focus → Durability-Focus.
- `bot.py` `place_ward()`: called at the **end** of each turn (moving the ward drops the old ward's vision, and units seen through it then throw "Unit is not in vision" if touched later that turn). Picks the ring-2 tile that reveals the most tiles we cannot see ourselves; hidden bush ×3, enemy-side ×2; only moves if 1.2× better than the current ward + 6. `ward_placement_tiles()` includes walls, and `Ward.visible_tiles_from` on a wall raises.
- `knowledge.py`: `bushes`, `walls`, `enemy_half` (tiles nearer the enemy spawn; built from Chebyshev rings, since a per-tile Python loop costs millions of fuel on 100×100 maps).
- Ward constants (probed): 1 active ward, 10-round cooldown, no expiry, vision 6, placement radius 2.

## Results (21 maps × both sides, 42 games per opponent; c3 = v1)

| Variant | vs c3 | Pool total | Deaths/game |
|---|---|---|---|
| c3 (v1) | — | 207/294 (pool without the c3 mirror) | 36.2 |
| `safe` = tank + wards + cautious | 35/42 | 290/336 | 23.7 |
| `s_tank` | 31/42 | 286/336 | |
| `s_wards` | 21/42 | 253/336 | |
| `s_caut` (FIGHT_EDGE 1.3, RETREAT 1.1, flee < 0.7, contest 2 turns) | 14/42 | 214/336 | 33.1 |
| `t_c` = tank + cautious | 27/42 (22/42 vs safe) | 259/336 | |
| `t_w` = tank + wards | 40/42 (25/42 vs safe) | 289/336 | |
| **v2** (= `t_w`, cleaned up) | **39/42** (25/42 vs safe) | **290/336** | 27.5 |

Pool for the last rows: c3, safe, c2, v7, v6trip, invader, monoallow, goldrush-bot. Patches: `tools/eval/patches/{tank,wards,cautious}.py`.

Caveat: every local opponent is our own lineage (aggressive, Monster/Power builds). The tank build wins the fights they pick; whether it holds against the ladder needs scrims.

## Platform

Submitted 2026-10-20 as platform version 12 (commit 952ae77).

Scrim vs Mommy Shogun (group `2c7db37b-d6a6-4a9e-958a-b53c753783b9`, we were team A): **0/5**, worse than v8's 1/5. The local gains did not transfer.

| Map | v8 gems, deaths | v2 gems, deaths | Mommy vs v2 |
|---|---|---|---|
| lanes | 838, 33 | 588, 30 | 1026, 4 |
| hooks | 66, 84 | 66, 79 | 1012, 14 |
| corners | 1016 (win), 4 | 97, 7 | 1000, 0 |
| elkring | 132, 10 | 539, 22 | 1001, 6 |
| eight | 815, 38 | 761, 41 | 1019, 22 |

- `corners`: not a fight loss and not banking (bags stayed at 0–44). We collected 344 gems but tributed 97; our camp clears per 200 rounds went 19, 14, 6, 4, 3 while theirs stayed at 7. Cause unknown; watch the replay.
- `hooks` (31×31): we died about every 20 rounds all game around (12–16, 10–17), the map centre: trickle-feeding a contested spot, as in v1's notes.

Scrims vs WHIM (62), smurphy (65), NotSoLonely (66) on corners, elkring, hooks, corridors, contest: **0/15**.

| Map | WHIM | smurphy | NotSoLonely |
|---|---|---|---|
| corners | 19–1037 | 665–1010 | 156–1015 |
| elkring | 528–1023 | 418–1012 | 352–1012 |
| hooks | 22–1012 (69 deaths) | 88–1012 (87) | 44–1012 (78) |
| corridors | 171–1016 | 454–1021 | 393–1010 |
| contest | 0–400 (95 deaths) | 0–1000 (98) | 0–600 (87) |

## Altar-lock oscillation (fixed after version 12; inherited from v1)

`corners` collapse, reproduced locally (v2 as A vs v7: 216–1003). An enemy lock sat on the central altar. `has_altar_lock()` is False whenever the altar is out of view, and `usable_altars()` dropped locked altars, so a carrier that saw the lock turned toward a corner altar 35 tiles away, lost sight of the lock a step later and turned back. Five champions oscillated at (26–27, 25–27) with full bags for hundreds of rounds. Ladder teams buy about 6 altar locks a game.

| Fix | Same game | Pool (c3, safe, c2, v7, v6trip, invader, monoallow, goldrush; 336) | vs v2 (version 12) |
|---|---|---|---|
| none (version 12) | 216–1003 | 290 | — |
| `lockfix`: never skip locked altars (tributing there hits the lock; 3 hits clear it) | 1031–317 | 287 | 17/42 |
| `lockmem`: remember a seen lock until that altar is seen clear | 1015–991 | 288 | 18/42 |

Locally neutral (our pool rarely locks altars); 17–18 of 42 is within noise of 21. `lockmem` is in `bots/v2` (`Knowledge.locked`), being closest to the old behaviour. `tools/eval/bots/c4` = version 12 as submitted.

## Team fights: `hooks` and `contest`

`01hooks` (31×31): the only altar is at (15, 15) inside a walled box, and all four gem groups ring the box. We die about every 20 rounds at (12–15, 8–19) all game (68–84 deaths vs 14–29). `00contest`: 24–40 deaths at one cell by the monolith. Both are the trickle-feeding problem from v1's notes: champions arrive one at a time at the one spot that matters and lose 1-v-3s. Fixing it needs squad play (gather, then enter together), not tuning.

Version 13 (= v2 + `lockmem`) re-scrim vs Mommy Shogun (group `3875cc35`): still 0/5, but **corners 97 → 611 gems** (5 deaths, lost 611–1027 in 951 rounds to a team with 0 deaths: a pure farming-speed loss). lanes 560–1020, hooks 66–1012 (identical to version 12: deterministic, no lock involved), elkring 550–1005, eight 761–1019.

Top-15 games on these maps are winner-take-all too: on `hooks` winners score 1,012 with about 12 deaths, losers 77 with 47; on `contest` losers score 0.

| Squad variant (pool c3, safe, c2, v7, v6trip, invader, monoallow, goldrush; 336) | Wins | Deaths/game | Median rounds |
|---|---|---|---|
| none (version 13) | 288 | 27.2 | 1,446 |
| `squad`: contested groups (enemy spawn ≤ 1.25× our distance) are shared, not split, and taken only once min(3, living slots) stand together at a staging point 9 tiles back (25-round cap) | 220 | 23.3 | 1,690 |
| `squad` + `squadmono`: only groups with strength ≥ 200 (monoliths) | 273 | 27.5 | 1,499 |

`squad` won contest 15/16 and eight 15/16, but hooks fell 14 → 7 and ambush, expanse, big-world, broken-curve fell to 6–8 of 16: staging before every contested group costs more farming than it saves in fights. Both rejected (patches kept). This is the fifth grouping idea to lose locally (`rally`, `regroup`, `packdeadly`, `monopack` before it).

## Ladder, wider view (2026-10-20 afternoon)

Since v2 went live (~07:53 UTC) the team climbed from rank 491 (1,424) to **295 (1,545)**: 64 of the last 100 ranked games won. The platform now shows our team name as "big".

36 ranked losses against about 20 different teams: **26 lost on fights** (we died 10+ more), 6 on farming speed (the Mommy Shogun pattern), 4 close. Median deaths 45 (us) vs 18 (them); median gems collected 733 vs 1,131.

| Map | Ranked record | What happens |
|---|---|---|
| `01elk_arena` | 1/5 | Only gem group is at the centre (72 gems, 8 tiles from each spawn). We die 84–154 times, mostly at (20–25, 20) between our spawn and the centre; they die 3–12. |
| `00eight` | 2/5 | 64–84 deaths vs 5–33. |
| `00lanes` | 2/7 | 21–49 deaths vs 5–9, mostly at x 35–50 on the top row (map centre). |
| `00elkring` | 2/8 | Mixed: 3 fight losses, 3 farming losses. |

The losses are trickle-feeding at the one contested spot, against many teams, not just Mommy Shogun.

## C++ vs Python (fuel probe, 2026-10-20)

Probe bots timed the same operations with `fuel_remaining()` (Python gets 2.5M per turn, C++ 100k):

| Operation | C++ | Python | Ratio |
|---|---|---|---|
| Full-map `DistanceField.compute` (lanes / big-world) | 5.2k / 30k | 150k / 792k | 26–29× |
| Bitboard union of 3 layers | 250–500 | 21k–27k | 55–82× |
| `vision.camps()` per camp | ~0.5–1k | ~37k | 40–60× |
| 1,000-iteration arithmetic loop | 7.7k | 524k | 68× |

So C++ has about the same budget for distance fields and 2–3× more for everything else. v2 uses a median 0.71M of 2.5M per turn (p90 1.46M, p99 1.92M) and is capped on 0.1% of turns; the fuel gates (re-plan > 1.5M, refine > 0.9M, ward > 1.2M) skip work on about 8% of turns. Compute is not what loses games, so a port alone would not make the bot stronger; it pays only for compute-hungry features (fight simulation, every-turn re-planning).

## Next

- Team fights / trickle-feeding: the main cause of ranked losses (26 of 36).
- Farming speed: Mommy Shogun beat us on `corners` and `elkring` with 0–2 deaths, so the gap there is pure farming, not fighting.
- Team fights on `hooks`/`contest`: grouping heuristics keep losing locally; our pool may simply not reward them (every pool bot trickle-feeds too).
- Deaths are still 27/game locally. Mommy-style avoidance (use ward sightings to leave a camp before the enemy arrives) is the untested half of the "safe farmer".
- `00elkring` vs Mommy Shogun: v8 froze at 132 gems from round 250 with only 10 deaths (collected 506, lost 242 on death, camp clears fell 9 → 2 per 250 rounds). Trace it.
- Draft variants from the ladder: Heart of Ruin instead of Cassi & Issac (Sponge, 33/50), Marcella on `ambush`/`big_world`/`concentrated_wealth`/`fracture` (LARP, 10/10).
