#!/bin/bash
# usage: econ.sh XDIR -- farming speed vs the starter bot: total rounds over all games (lower is better)
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
X=$(realpath "$1"); name=$(basename "$X"); mkdir -p "$S/work"
python3 "$S/evalbots.py" "$X" starter-python > "$S/work/econ_$name.txt" 2>&1
grep ^RES "$S/work/econ_$name.txt" | awk '{w+=$4; r+=$7; printf "%s:%s ", $2$3, $7} END{printf "\nECON %s: wins %d/%d total rounds %d\n", "'$name'", w, NR, r}'
