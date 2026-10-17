#!/bin/bash
# usage: OPPS="a b" sweep.sh variant... -- evaluate each bots/<variant> against OPPS in turn; summary.py tabulates
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPPS=${OPPS:-"monoallow tribfix v6trip goldrush-bot starter-python"}
mkdir -p "$S/work"
for v in "$@"; do
  args=()
  for o in $OPPS; do if [ -d "$S/bots/$o" ]; then args+=("$S/bots/$o"); else args+=("$o"); fi; done
  python3 "$S/evalbots.py" "$S/bots/$v" "${args[@]}" > "$S/work/p_$v.txt" 2>&1
  echo "$(date +%H:%M:%S) $(grep ^TOTAL "$S/work/p_$v.txt")"
done
