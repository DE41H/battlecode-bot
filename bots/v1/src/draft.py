"""Draft: pick a farming composition and record it for the champions."""

import cambc
from memory import encode_plan

Pick, Team = cambc.ChampionDraft, cambc.Team

# Picks are simultaneous and not exclusive, so this is purely our preferred composition.
# The top of the ladder converges on Cassi & Issac, Stellar, Ren, Varg and Ryth.
PRIORITY = [
    Pick.CASSI_AND_ISSAC,
    Pick.STELLAR,
    Pick.REN,
    Pick.VARG,
    Pick.RYTH,
    Pick.TAVI,
    Pick.VENDETTA,
    Pick.MARCELLA,
    Pick.VESPER_VALE,
    Pick.PRISM,
    Pick.WILLOW,
]


def play():
    chosen = cambc.draft.current_draft(Team.ALLY)
    remaining = [pick for pick in PRIORITY if pick not in chosen]
    pick = remaining[0]
    picks = [*chosen, pick]

    # Pick first: later draft turns get only ordinary fuel, and a bot that runs dry is given random picks.
    cambc.draft.pick(pick)
    # Rewrite the plan every pick; the last write is what champions read. Zones are no longer used.
    cambc.draft_memory.submit(encode_plan(picks, []))
