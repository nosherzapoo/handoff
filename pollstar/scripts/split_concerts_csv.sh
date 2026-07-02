#!/usr/bin/env bash
#
# split_concerts_csv.sh
# Split concerts.csv into 7 smaller files for sharing (email, upload limits).
# Each part includes the header row so it opens standalone.
#
# Author: Nosher Ali Khan
# Last updated: 2026-07-02
#
# Usage (run from the project root):
#   ./pollstar/scripts/split_concerts_csv.sh          # writes concerts_part1_of_7.csv ... part7_of_7.csv
#   ./pollstar/scripts/split_concerts_csv.sh N        # split into N parts instead of 7

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"   # scripts live in pollstar/scripts/, data at project root
cd "$PROJECT_ROOT"

PARTS="${1:-7}"
SRC="concerts.csv"

if [ ! -f "$SRC" ]; then
  echo "ERROR: $SRC not found. Run ./pollstar/scripts/refresh_data.sh first." >&2
  exit 1
fi

echo "Splitting $SRC into $PARTS parts (each with a header) ..."

# Remove any stale parts from a previous run.
rm -f concerts_part*_of_*.csv

awk -v parts="$PARTS" '
  NR == 1 { header = $0; next }                 # capture header, do not emit yet
  { rows[NR] = $0; n++ }
  END {
    per = int((n + parts - 1) / parts)          # ceil(rows / parts)
    idx = 0; count = 0
    for (i = 2; i <= NR; i++) {
      if (count % per == 0) {
        idx++
        fname = sprintf("concerts_part%d_of_%d.csv", idx, parts)
        print header > fname
      }
      print rows[i] >> fname
      count++
    }
  }
' "$SRC"

echo "Done:"
ls -lh concerts_part*_of_*.csv
