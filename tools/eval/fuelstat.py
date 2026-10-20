"""Share of play turns at the fuel cap, per kept replay: python fuelstat.py BATCH_DIR"""
import glob, io, os, statistics, struct, sys, zipfile

for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.repl26a"))):
    z = zipfile.ZipFile(path)
    out = []
    for team in "ab":
        b = z.read(f"team-{team}.fuel")
        vals = [struct.unpack_from("<Q", b, 13 + 8 * i)[0] for i in range((len(b) - 13) // 8)]
        play = [v for v in vals[13:]]
        cap = sum(v >= 2_500_000 for v in play)
        out.append(f"{team}: cap {cap / max(1, len(play)):4.0%} med {statistics.median(play) / 1e6:.2f}M")
    print(f"{os.path.basename(path)[:40]:40s}", "  ".join(out))
