"""Build orders: which shards each champion buys, and consumables to keep stocked."""

import cambc

Item, Kind, Consumable = cambc.ItemType, cambc.ChampionType, cambc.ConsumableType

# Each step is (shard, total copies wanted); five shards combine into that family's emblem.
STRENGTH_FARMER = [
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_STRENGTH, 60),
]
TANK = [
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.POWER_SHARD_OF_STRENGTH, 60),
]
CASTER = [
    (Item.MONSTER_SHARD_OF_FOCUS, 5),
    (Item.JUNGLE_SHARD_OF_HEALTH, 5),
    (Item.POWER_SHARD_OF_FOCUS, 60),
]
GOLD_FARMER = [
    (Item.TREASURE_SHARD_OF_STRENGTH, 5),
    (Item.MONSTER_SHARD_OF_STRENGTH, 5),
    (Item.POWER_SHARD_OF_STRENGTH, 60),
]

BUILDS = {
    Kind.VENDETTA: STRENGTH_FARMER,
    Kind.ISSAC: STRENGTH_FARMER,
    Kind.VARG: STRENGTH_FARMER,
    Kind.REN: STRENGTH_FARMER,
    Kind.RYTH: TANK,
    Kind.MARCELLA: TANK,
    Kind.VESPER_VALE: GOLD_FARMER,
    Kind.STELLAR: CASTER,
    Kind.PRISM: CASTER,
    Kind.CASSI: CASTER,
    Kind.TAVI: CASTER,
    Kind.WILLOW: CASTER,
}

# Emblem produced by five shards of a kind; owned emblems count as five shards each.
_EMBLEM = {Item(i): Item(i + 1) for i in range(0, Item.COUNT, 2)}


def owned(counts, shard):
    return counts[int(shard)] + shard.combine_count() * counts[int(_EMBLEM[shard])]


def shop():
    """Spend gold down the champion's build order; keep an altar lock in stock."""
    me = cambc.me()
    build = BUILDS.get(me.champion_name(), STRENGTH_FARMER)

    # An altar lock is cheap insurance for denying enemy tributes.
    try:
        if me.gold_count() >= 40 and me.can_buy(Consumable.ALTAR_LOCK):
            me.buy(Consumable.ALTAR_LOCK)
    except cambc.Error:
        pass

    for shard, wanted in build:
        counts = me.item_count()
        missing = wanted - owned(counts, shard)
        if missing <= 0:
            continue
        count = min(missing, me.gold_count() // shard.cost())
        if count <= 0:
            return
        try:
            if me.can_buy(shard, count):
                me.buy(shard, count)
        except cambc.Error:
            return
        if count < missing:
            return
