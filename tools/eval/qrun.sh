#!/bin/bash
# Sequential eval queue: each line of work/queue.txt is "variant [opps...]"; results append to work/results.txt.
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$S/work"; touch "$S/work/queue.txt" "$S/work/done.txt"
while true; do
  line=$(grep -vxF -f "$S/work/done.txt" "$S/work/queue.txt" | head -1)
  if [ -z "$line" ]; then sleep 20; continue; fi
  set -- $line; v=$1; shift
  out=$("$S/pool.sh" "$S/bots/$v" "$@")
  { echo "$(date +%H:%M) $line"; echo "$out"; } >> "$S/work/results.txt"
  echo "$line" >> "$S/work/done.txt"
done
