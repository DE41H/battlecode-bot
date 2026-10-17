#!/bin/bash
# usage: profile.sh VARIANT [OPP] -- traced games of bots/VARIANT (DEBUG on) on every map; share of champion turns per mode
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v=$1; o=${2:-starter-python}
BASE="$S/bots/$v" "$S/mkpatch.sh" "prof-$v" debugon >/dev/null
python3 "$S/evalbots.py" "$S/bots/prof-$v" "$o" --keep > "$S/work/prof_$v.txt" 2>&1
d=$(ls -td "$S"/work/batch/prof-$v-* | head -1)
for f in "$d"/*-xA.repl26a; do
  m=$(basename "$f" .repl26a); t=$(mktemp -d)
  (cd "$t" && unzip -o -q "$f" team-a.stdout && tr -cd '\11\12\40-\176' < team-a.stdout | sed 's/^ *//' | awk -v m="${m#*-}" 'NF==12 && $1 ~ /^[0-9]+$/ {print m, $NF}')
  rm -rf "$t"
done | awk '{c[$2]++; n++; per[$1" "$2]++; tot[$1]++} END{for (k in c) printf "%-12s %5.1f%%\n", k, 100*c[k]/n; }' | sort -k2 -nr
rm -rf "$d"
