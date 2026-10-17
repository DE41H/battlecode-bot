import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Jungle first (30% less camp damage makes solo farming safe), in the champion's damage stat.
edit(D + "shop.py", [
("""STRENGTH_FARMER = [
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),""", """STRENGTH_FARMER = [
    (Item.JUNGLE_SHARD_OF_STRENGTH, 5),
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),"""),
("""CASTER = [
    (Item.MONSTER_SHARD_OF_FOCUS, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),""", """CASTER = [
    (Item.JUNGLE_SHARD_OF_FOCUS, 5),
    (Item.MONSTER_SHARD_OF_FOCUS, 5),"""),
])
