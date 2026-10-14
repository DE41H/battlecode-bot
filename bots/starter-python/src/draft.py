import cambc
from randomness import below


def play():
    # Choose randomly from the champions our team has not picked.
    chosen = cambc.draft.current_draft(cambc.Team.ALLY)
    available = [pick for pick in cambc.ChampionDraft if pick not in chosen]

    # Draft memory starts at byte zero and is copied to each champion.
    cambc.draft_memory.submit(b"hello world")
    cambc.draft.pick(available[below(len(available))])
