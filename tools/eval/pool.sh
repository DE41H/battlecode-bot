#!/bin/bash
# usage: pool.sh XDIR [opps...] -- X vs each opponent in bots/, all maps, both sides, as one batch; prints per-opponent and total lines
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
X=$(realpath "$1"); shift
OPPS=${@:-"monoallow tribfix v6trip goldrush-bot"}
name=$(basename "$X")
mkdir -p "$S/work"
args=()
for o in $OPPS; do if [ -d "$S/bots/$o" ]; then args+=("$S/bots/$o"); else args+=("$o"); fi; done
python3 "$S/evalbots.py" "$X" "${args[@]}" > "$S/work/p_${name}.txt" 2>&1
grep -E "^vs |^TOTAL" "$S/work/p_${name}.txt" | sed 's/^vs /  vs /'
