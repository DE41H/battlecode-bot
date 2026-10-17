import sys


def edit(path, pairs):
    s = open(path).read()
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {old[:60]!r} x{s.count(old)}"
        s = s.replace(old, new)
    open(path, "w").write(s)


def append(path, text):
    open(path, "a").write(text)


D = sys.argv[1] + "/"
