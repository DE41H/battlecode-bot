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

## Next

- Submit the lock fix and re-scrim `corners` and `elkring` to confirm the collapse is gone on the ladder.
- Squad play for single-objective maps (`hooks`, `contest`, `corridors`).
- Deaths are still 27/game locally. Mommy-style avoidance (use ward sightings to leave a camp before the enemy arrives) is the untested half of the "safe farmer".
- `00elkring` vs Mommy Shogun: v8 froze at 132 gems from round 250 with only 10 deaths (collected 506, lost 242 on death, camp clears fell 9 → 2 per 250 rounds). Trace it.
- Draft variants from the ladder: Heart of Ruin instead of Cassi & Issac (Sponge, 33/50), Marcella on `ambush`/`big_world`/`concentrated_wealth`/`fracture` (LARP, 10/10).
