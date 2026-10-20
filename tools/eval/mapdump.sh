#!/bin/bash
# usage: mapdump.sh MAP... -- ASCII map, groups and camp designs for each map, into work/maps/MAP.txt
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$S/../.." && pwd)"
"$S/mkpatch.sh" mapdump mapdump >/dev/null
export CAMBC_WASMTIME_CACHE=${CAMBC_WASMTIME_CACHE:-$S/work/wtcache}
mkdir -p "$S/work/maps"
for m in "$@"; do
  d="$S/work/runs/md-$m"; rm -rf "$d"; mkdir -p "$d"
  (cd "$R" && cambc run "$S/bots/mapdump" "$R/bots/starter-python" --map "$R/maps/$m.map26a" --rounds 4 --fuel 50000000 -o "$d" >/dev/null 2>&1)
  (cd "$d" && unzip -o -q *.repl26a && tr -cd '\11\12\40-\176' < team-a.stdout | sed 's/^ *//' > "$S/work/maps/$m.txt")
  echo "$m: $(grep -c GROUP "$S/work/maps/$m.txt") groups"
done
