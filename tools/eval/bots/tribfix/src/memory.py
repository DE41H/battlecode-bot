"""Team memory layouts.

Draft memory (written by the draft bot, read-only afterwards):
    byte 0       format version
    byte 1       number of picks P
    bytes 2..    P champion-draft values, in pick order
    next byte    number of camp groups G
    next G bytes zone owner (pick index) per group, 255 for shared

Shared memory (8 bytes, live): byte i is the camp group claimed by pick slot i, plus one; 0 is no claim.
"""

import cambc

VERSION = 1
SHARED = 255
CLAIM_SLOTS = 8

Kind, Pick = cambc.ChampionType, cambc.ChampionDraft

# Champion bodies that belong to each draft pick.
_PICK_OF = {
    Kind.RYTH: Pick.RYTH,
    Kind.VESPER_VALE: Pick.VESPER_VALE,
    Kind.VENDETTA: Pick.VENDETTA,
    Kind.CASSI: Pick.CASSI_AND_ISSAC,
    Kind.ISSAC: Pick.CASSI_AND_ISSAC,
    Kind.STELLAR: Pick.STELLAR,
    Kind.PRISM: Pick.PRISM,
    Kind.MARCELLA: Pick.MARCELLA,
    Kind.WILLOW: Pick.WILLOW,
    Kind.REN: Pick.REN,
    Kind.VARG: Pick.VARG,
    Kind.TAVI: Pick.TAVI,
}


def encode_plan(picks, zones):
    data = bytearray([VERSION, len(picks)])
    data += bytes(int(pick) for pick in picks)
    data.append(len(zones))
    data += bytes(zones)
    return bytes(data)


class Plan:
    """Decoded draft plan; empty when the draft bot wrote nothing usable."""

    def __init__(self):
        self.picks = []
        self.zones = []
        try:
            raw = bytes(cambc.DraftMemoryBuffer())
        except Exception:
            return
        if len(raw) < 2 or raw[0] != VERSION:
            return
        count = raw[1]
        self.picks = list(raw[2 : 2 + count])
        offset = 2 + count
        if offset < len(raw):
            groups = raw[offset]
            self.zones = list(raw[offset + 1 : offset + 1 + groups])

    def slot_of(self, champion_type):
        pick = _PICK_OF.get(champion_type)
        if pick is None or int(pick) not in self.picks:
            return None
        return self.picks.index(int(pick))

    def zone_of(self, group_index):
        if group_index < len(self.zones):
            return self.zones[group_index]
        return SHARED


def read_claims():
    data = bytearray(CLAIM_SLOTS)
    cambc.shared_memory.read(0, data)
    return [value - 1 if value else None for value in data]


def write_claim(slot, group_index):
    if slot is None or not 0 <= slot < CLAIM_SLOTS:
        return
    cambc.shared_memory[slot] = 0 if group_index is None else group_index + 1
