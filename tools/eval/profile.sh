#!/bin/bash
# usage: profile.sh VARIANT [OPP] -- traced games of bots/VARIANT (DEBUG on) on every map; share of champion turns per mode
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v=$1; o=${2:-starter-python}
BASE="$S/bots/$v" "$S/mkpatch.sh" "prof-$v" debugon >/dev/null
python3 "$S/evalbots.py" "$S/bots/prof-$v" "$o" --keep > "$S/work/prof_$v.txt" 2>&1
d=$(ls -td "$S"/work/batch/prof-$v-* | head -1)
for f in "$d"/*-xA.repl26a; do
  m=$(basename "$f" .repl26a); t=$(mktemp -d)
  (cd "$t" && unzip -o -q "$f" team-a.stdout && tr -cd '\11\12\40-\176' < team-a.stdout | sed 's/^ *//' | awk -v m="${m#*-}" 'NF==12 && $1 ~ /^[0-9]+$/ {print m, $3, $NF}')
  rm -rf "$t"
done > "$S/work/prof_$v.modes"
awk '{c[$3]++; n++} END{for (k in c) printf "%-12s %5.1f%%\n", k, 100*c[k]/n; }' "$S/work/prof_$v.modes" | sort -k2 -nr
if [ -n "$BYTYPE" ]; then
  echo "--- by champion type (ChampionType: 0 Ryth 2 Vendetta 3 Cassi 4 Issac 5 Stellar 9 Ren 10 Varg) ---"
  awk '{c[$2" "$3]++; t[$2]++} END{for (k in c) {split(k, a, " "); printf "type %-3s %-12s %5.1f%%\n", a[1], a[2], 100*c[k]/t[a[1]]}}' "$S/work/prof_$v.modes" | sort -k2,2n -k4nr | awk '$4+0 >= 4'
fi
rm -rf "$d"
