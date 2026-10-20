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

## Next

- Scrim v2 against Mommy Shogun (`94fc1e5a-b5a7-4196-b076-bd47fbc7ca49`) and a couple of top-50 teams; this needs v2 submitted, since scrims play the current submission.
- Deaths are still 27/game locally. Mommy-style avoidance (use ward sightings to leave a camp before the enemy arrives) is the untested half of the "safe farmer".
- `00elkring` vs Mommy Shogun: v8 froze at 132 gems from round 250 with only 10 deaths (collected 506, lost 242 on death, camp clears fell 9 → 2 per 250 rounds). Trace it.
- Draft variants from the ladder: Heart of Ruin instead of Cassi & Issac (Sponge, 33/50), Marcella on `ambush`/`big_world`/`concentrated_wealth`/`fracture` (LARP, 10/10).
