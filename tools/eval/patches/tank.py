import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Tank builds copied from Mommy Shogun (rank 71, 36/50 on engine 1.0.0): Jungle first, then Durability and Bruiser emblems.
edit(D + "shop.py", [
("""BUILDS = {""", """# Each emblem is 5 shards; totals are cumulative per shard kind, so repeated Bruiser steps buy another emblem.
J_H, J_S = Item.JUNGLE_SHARD_OF_HEALTH, Item.JUNGLE_SHARD_OF_STRENGTH
D_S, D_H, D_F = Item.DURABILITY_SHARD_OF_STRENGTH, Item.DURABILITY_SHARD_OF_HEALTH, Item.DURABILITY_SHARD_OF_FOCUS
B_S, B_H, B_F = Item.BRUISER_SHARD_OF_STRENGTH, Item.BRUISER_SHARD_OF_HEALTH, Item.BRUISER_SHARD_OF_FOCUS
M_S = Item.MONSTER_SHARD_OF_STRENGTH
TANK_MELEE = [(J_H, 5), (D_S, 5), (B_H, 5), (M_S, 5), (B_H, 10), (B_S, 60)]
TANK_REN = [(J_H, 5), (B_H, 5), (D_S, 5), (B_H, 10), (B_S, 60)]
TANK_RYTH = [(J_H, 5), (D_S, 5), (B_H, 60)]
TANK_VARG = [(J_S, 5), (D_H, 5), (B_S, 10), (B_H, 5), (B_S, 60)]
TANK_CASTER = [(B_F, 10), (B_H, 5), (B_F, 15), (D_F, 5), (B_F, 60)]

BUILDS = {"""),
])
edit(D + "shop.py", [
("""    Kind.TAVI: CASTER,
    Kind.WILLOW: CASTER,
}""", """    Kind.TAVI: CASTER,
    Kind.WILLOW: CASTER,
}
BUILDS.update({
    Kind.ISSAC: TANK_MELEE,
    Kind.VENDETTA: TANK_MELEE,
    Kind.MARCELLA: TANK_MELEE,
    Kind.REN: TANK_REN,
    Kind.RYTH: TANK_RYTH,
    Kind.VARG: TANK_VARG,
    Kind.STELLAR: TANK_CASTER,
    Kind.CASSI: TANK_CASTER,
    Kind.PRISM: TANK_CASTER,
    Kind.TAVI: TANK_CASTER,
})"""),
])
