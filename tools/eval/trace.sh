#!/bin/bash
# usage: trace.sh MAP [OPP] -- current bots/v1 with DEBUG on (plus visible camp HP) as team A; cleaned trace in work/runs/tr-MAP/a.txt
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$S/../.." && pwd)"
m=$1; o=${2:-tribfix}
"$S/mkpatch.sh" tprobe hplog ${EXTRA} >/dev/null
export CAMBC_WASMTIME_CACHE=${CAMBC_WASMTIME_CACHE:-$S/work/wtcache}
d="$S/work/runs/tr-$m"; rm -rf "$d"; mkdir -p "$d"; cd "$R"
opp="$S/bots/$o"; [ -d "$opp" ] || opp="$R/bots/$o"
cambc run "$S/bots/tprobe" "$opp" --map "$R/maps/$m.map26a" -o "$d" 2>&1 | grep -A3 "team bot"
cd "$d" && unzip -o -q *.repl26a && tr -cd '\11\12\40-\176' < team-a.stdout | sed 's/^ *//' > a.txt
grep -i "error" a.txt | sort | uniq -c | head
awk 'NF==12 && $1 ~ /^[0-9]+$/ {c[$2" "$3" "$NF]++} END{for(k in c) print k, c[k]}' a.txt | sort -k1,1n -k4nr | column -t
