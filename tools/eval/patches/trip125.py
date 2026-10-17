import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# A heal trip is a recall plus one walk back, not two walks.
edit(D + "knowledge.py", [("2.5 * info.spawn_distance + recall", "1.25 * info.spawn_distance + recall")])
