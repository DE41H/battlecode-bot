import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
edit(D + "draft.py", [("""    Pick.CASSI_AND_ISSAC,
""", "")])
