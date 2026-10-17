import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
import re
from _lib import D
s = open(D + "draft.py").read()
s, n = re.subn(r"PRIORITY = \[\n.*?\]", "PRIORITY = [\n" + '    Pick.CASSI_AND_ISSAC,\n    Pick.STELLAR,\n    Pick.REN,\n    Pick.VARG,\n    Pick.RYTH,\n    Pick.TAVI,\n    Pick.VENDETTA,\n    Pick.MARCELLA,\n    Pick.VESPER_VALE,\n    Pick.PRISM,\n    Pick.WILLOW,\n' + "]", s, flags=re.S)
assert n == 1
open(D + "draft.py", "w").write(s)
