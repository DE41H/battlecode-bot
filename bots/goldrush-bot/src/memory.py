"""Team memory layouts — goldrush-bot v2.

Draft memory (1024 bytes, written during draft, read-only in-match):

  Byte 0          version = 2
  Byte 1          P = number of picks (3–5)
  Bytes 2..2+P-1  ChampionDraft int per pick, in draft order

  Byte 2+P        G = number of camp groups
  Bytes [+1..+G]  zone_owner[group]     pick-slot index that owns it, 255 = shared
  Bytes [+1..+G]  group_priority[group] 0 = high, 1 = normal, 2 = low

  Bytes [+0..+P-1] role[slot]           0=anchor/Tavi, 1=support/Willow,
                                         2=econ/Vale,   3=fighter
  Bytes [+0..+P-1] bank_thresh[slot]    carried gems ÷ 5  (30→6, 45→9, 60→12)

  Byte             tavi_slot            pick-slot index, 255 = not drafted
  Byte             willow_slot
  Byte             vale_slot

Shared memory (8 bytes, live throughout match):

  Byte 0–4   claim[slot]   camp group index + 1  (0 = no claim)
  Byte 5     status flags  bit i = slot i
               bits 0–4   "I am banking / heading to altar"
               bit 5      monolith is down (any champion who sees it dead sets this)
               bit 6      distress (being chased with gems; nearby allies may help)
               bit 7      spare
  Byte 6     gem-load flags  bit i = slot i
               bits 0–4   "I am carrying ≥ 30 gems"
               bits 5–7   spare
  Byte 7     Tavi anchor   group index + 1 of Tavi's current camp (Willow reads this)
               0 = Tavi dead / unknown

Write discipline: each champion is sole writer of its own claim byte and its own
bits in bytes 5 and 6.  Tavi is sole writer of byte 7.  Read-modify-write for
the flag bytes is safe because champions act sequentially within a round.
"""

import cambc

VERSION = 2

# Roles stored in draft memory.
ROLE_ANCHOR  = 0   # Tavi: never recalls, bank early, buy in field
ROLE_SUPPORT = 1   # Willow: stay near Tavi, heal-first priority
ROLE_ECON    = 2   # Vesper Vale: recall at 80g, gold-camp zone
ROLE_FIGHTER = 3   # everyone else: standard 60-gem banking

# Group priority tiers.
PRIO_HIGH   = 0    # Elk, Monolith
PRIO_NORMAL = 1    # Wolf, Gem cluster
PRIO_LOW    = 2    # Gold cluster

SHARED      = 255  # zone_owner or slot value meaning "not assigned"
CLAIM_SLOTS = 8    # shared memory has room for up to 8 champion slots

# Byte offsets in shared memory.
_OFF_CLAIM   = 0   # bytes 0-4
_OFF_FLAGS   = 5   # byte 5
_OFF_GEMS    = 6   # byte 6
_OFF_TAVI    = 7   # byte 7

Kind, Pick = cambc.ChampionType, cambc.ChampionDraft

_PICK_OF = {
    Kind.RYTH:        Pick.RYTH,
    Kind.VESPER_VALE: Pick.VESPER_VALE,
    Kind.VENDETTA:    Pick.VENDETTA,
    Kind.CASSI:       Pick.CASSI_AND_ISSAC,
    Kind.ISSAC:       Pick.CASSI_AND_ISSAC,
    Kind.STELLAR:     Pick.STELLAR,
    Kind.PRISM:       Pick.PRISM,
    Kind.MARCELLA:    Pick.MARCELLA,
    Kind.WILLOW:      Pick.WILLOW,
    Kind.REN:         Pick.REN,
    Kind.VARG:        Pick.VARG,
    Kind.TAVI:        Pick.TAVI,
}


# ── encoding ──────────────────────────────────────────────────────────────────

def encode_plan(picks, zones, priorities, roles, bank_thresholds,
                tavi_slot, willow_slot, vale_slot):
    """Serialise the full draft plan into draft-memory bytes."""
    P = len(picks)
    G = len(zones)
    assert len(priorities) == G
    assert len(roles) == P
    assert len(bank_thresholds) == P

    data = bytearray()
    data.append(VERSION)
    data.append(P)
    data += bytes(int(p) for p in picks)
    data.append(G)
    data += bytes(zones)        # zone_owner per group
    data += bytes(priorities)   # group_priority per group
    data += bytes(roles)        # role per slot
    data += bytes(bank_thresholds)  # bank_thresh per slot (gems÷5)
    data.append(tavi_slot   if tavi_slot   is not None else SHARED)
    data.append(willow_slot if willow_slot is not None else SHARED)
    data.append(vale_slot   if vale_slot   is not None else SHARED)
    return bytes(data)


# ── decoding ──────────────────────────────────────────────────────────────────

class Plan:
    """Decoded draft plan; safe defaults when draft bot wrote nothing usable."""

    def __init__(self):
        self.picks:          list[int] = []
        self.zones:          list[int] = []
        self.priorities:     list[int] = []
        self.roles:          list[int] = []
        self.bank_thresholds: list[int] = []
        self.tavi_slot:   int | None = None
        self.willow_slot: int | None = None
        self.vale_slot:   int | None = None

        try:
            raw = bytes(cambc.DraftMemoryBuffer())
        except Exception:
            return

        if len(raw) < 2 or raw[0] != VERSION:
            return

        P = raw[1]
        if len(raw) < 2 + P + 1:
            return
        self.picks = list(raw[2 : 2 + P])

        offset = 2 + P
        G = raw[offset];  offset += 1
        if len(raw) < offset + 2 * G + 2 * P + 3:
            return

        self.zones      = list(raw[offset : offset + G]);  offset += G
        self.priorities = list(raw[offset : offset + G]);  offset += G
        self.roles      = list(raw[offset : offset + P]);  offset += P
        self.bank_thresholds = list(raw[offset : offset + P]); offset += P

        def _slot(v):
            return None if v == SHARED else v

        self.tavi_slot   = _slot(raw[offset]);     offset += 1
        self.willow_slot = _slot(raw[offset]);     offset += 1
        self.vale_slot   = _slot(raw[offset])

    # ── helpers ───────────────────────────────────────────────────────────────

    def slot_of(self, champion_type):
        pick = _PICK_OF.get(champion_type)
        if pick is None or int(pick) not in self.picks:
            return None
        return self.picks.index(int(pick))

    def zone_of(self, group_index):
        if group_index < len(self.zones):
            return self.zones[group_index]
        return SHARED

    def priority_of(self, group_index):
        if group_index < len(self.priorities):
            return self.priorities[group_index]
        return PRIO_NORMAL

    def role_of(self, slot):
        if slot is not None and slot < len(self.roles):
            return self.roles[slot]
        return ROLE_FIGHTER

    def bank_threshold(self, slot):
        """Return the carrying-gem threshold at which this slot should bank."""
        if slot is not None and slot < len(self.bank_thresholds):
            return self.bank_thresholds[slot] * 5
        return 60


# ── shared memory helpers ─────────────────────────────────────────────────────

def _read_byte(offset):
    buf = bytearray(1)
    cambc.shared_memory.read(offset, buf)
    return buf[0]


def _write_byte(offset, value):
    cambc.shared_memory.write(offset, bytes([value & 0xFF]))


def _set_bit(offset, bit, value):
    """Read-modify-write a single bit in a shared memory byte (safe: sequential turns)."""
    current = _read_byte(offset)
    if value:
        current |= (1 << bit)
    else:
        current &= ~(1 << bit)
    _write_byte(offset, current)


# Claim bytes 0-4 (one per slot).
def read_claims():
    data = bytearray(CLAIM_SLOTS)
    cambc.shared_memory.read(0, data)
    return [v - 1 if v else None for v in data]


def write_claim(slot, group_index):
    if slot is None or not 0 <= slot < CLAIM_SLOTS:
        return
    cambc.shared_memory[slot] = 0 if group_index is None else group_index + 1


# Byte 5 — status flags.
def write_banking(slot, is_banking):
    """Set/clear the 'I am banking' bit for this slot in byte 5."""
    if slot is None or not 0 <= slot < 5:
        return
    _set_bit(_OFF_FLAGS, slot, is_banking)


def write_monolith_down(is_down):
    """Any champion that sees the monolith dead broadcasts this."""
    _set_bit(_OFF_FLAGS, 5, is_down)


def write_distress(slot, in_distress):
    """Set/clear the distress bit (being chased with gems)."""
    if slot is None or not 0 <= slot < 5:
        return
    _set_bit(_OFF_FLAGS, 6, in_distress)


def read_banking_flags():
    """Bitmask of slots currently banking (bits 0-4 of byte 5)."""
    return _read_byte(_OFF_FLAGS) & 0x1F


def read_monolith_down():
    return bool(_read_byte(_OFF_FLAGS) & (1 << 5))


def read_distress():
    return bool(_read_byte(_OFF_FLAGS) & (1 << 6))


# Byte 6 — gem-load flags.
def write_heavy_gems(slot, is_heavy):
    """Set/clear the 'carrying ≥ 30 gems' bit for this slot."""
    if slot is None or not 0 <= slot < 5:
        return
    _set_bit(_OFF_GEMS, slot, is_heavy)


def read_heavy_gem_flags():
    """Bitmask of slots carrying heavy gems (bits 0-4 of byte 6)."""
    return _read_byte(_OFF_GEMS) & 0x1F


# Byte 7 — Tavi anchor.
def write_tavi_group(group_index):
    """Tavi writes its current camp group so Willow can follow."""
    _write_byte(_OFF_TAVI, 0 if group_index is None else group_index + 1)


def read_tavi_group():
    """Returns group index Tavi is farming, or None."""
    v = _read_byte(_OFF_TAVI)
    return None if v == 0 else v - 1
