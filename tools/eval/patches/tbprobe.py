import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _lib import D, edit
# Probe: print a short traceback with each bot error.
edit(D + "main.py", [("""            print(f"bot error: {error!r}", flush=True)""", """            import traceback
            tb = traceback.extract_tb(error.__traceback__)
            print(f"bot error: {error!r}", " < ".join(f"{f.name}:{f.lineno}" for f in reversed(tb)), flush=True)""")])
