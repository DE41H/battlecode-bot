import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Hostile camps are the awake armed ones (vision.awake_camp_tiles), not the damaged ones: a full-health camp
# woken by a hit on its group kept interrupting our recalls until we died ("low-recall" was the commonest
# last mode before a camp death in a traced 01corridors game). Apply after campsafe.
edit(D + "bot.py", [
("""        hostile_camps = [
            camp
            for camp, _, hp in k.seen
            if hp > 0 and camp.strength() > 0 and hp < camp.max_health()
        ]""", """        # Awake, armed camps: a hit on any camp wakes its whole group, full-health members included.
        awake = cambc.vision.awake_camp_tiles()
        k.awake = awake
        hostile_camps = [
            camp
            for camp, _, hp in k.seen
            if hp > 0 and camp.strength() > 0 and awake.is_set(camp.position())
        ]"""),
("""            if strength <= 0 or (index != self.target and hp >= camp.max_health()):""",
 """            if strength <= 0 or (
                index != self.target and not self.k.awake.is_set(camp.position())
            ):"""),
])
edit(D + "knowledge.py", [
("""        # This turn's visible camps as (camp, group index, health), filled by observe.
        self.seen = []""", """        # This turn's visible camps as (camp, group index, health), filled by observe.
        self.seen = []
        # Tiles of this turn's visible awake camps, filled by Bot.decide.
        self.awake = cambc.Bitboard()"""),
])
