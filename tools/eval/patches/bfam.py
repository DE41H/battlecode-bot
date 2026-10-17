import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# One emblem per useful family for its passive, all in the damage stat, then Power for raw stats.
edit(D + "shop.py", [
("""STRENGTH_FARMER = [
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_STRENGTH, 60),""", """STRENGTH_FARMER = [
    (Item.JUNGLE_SHARD_OF_STRENGTH, 5),
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.DURABILITY_SHARD_OF_STRENGTH, 5),
    (Item.BRUISER_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_STRENGTH, 60),"""),
("""CASTER = [
    (Item.MONSTER_SHARD_OF_FOCUS, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_FOCUS, 60),""", """CASTER = [
    (Item.JUNGLE_SHARD_OF_FOCUS, 5),
    (Item.MONSTER_SHARD_OF_FOCUS, 5),
    (Item.DURABILITY_SHARD_OF_FOCUS, 5),
    (Item.BRUISER_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_FOCUS, 60),"""),
])
