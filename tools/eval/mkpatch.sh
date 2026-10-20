#!/bin/bash
# usage: mkpatch.sh NAME PATCH... -- copy bots/v1 to bots/NAME and apply patches/PATCH.py to it in order
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$S/../.." && pwd)"
name=$1; shift
rm -rf "$S/bots/$name"; mkdir -p "$S/bots/$name"; cp -r "${BASE:-$R/bots/v1}/src" "$S/bots/$name/"
for p in "$@"; do python3 "$S/patches/$p.py" "$S/bots/$name/src" || { echo "PATCH $p FAILED"; exit 1; }; done
echo "built $name"
