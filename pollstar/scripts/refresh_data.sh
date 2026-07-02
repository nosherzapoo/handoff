#!/usr/bin/env bash
#
# refresh_data.sh
# Pull the latest Pollstar Boxoffice data and rebuild concerts.csv.
#
# Author: Nosher Ali Khan
# Last updated: 2026-07-02
#
# Usage (run from the project root):
#   ./pollstar/scripts/refresh_data.sh          # fetch missing pages, then rebuild concerts.csv
#   ./pollstar/scripts/refresh_data.sh --fresh  # delete the page cache first, then do a full pull
#   ./pollstar/scripts/refresh_data.sh --csv    # rebuild concerts.csv from cache only, no network
#
# Requires a valid token in jwt.txt at the project root. See pollstar/README.md sections 3 and 4.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"   # scripts live in pollstar/scripts/, data at project root
cd "$PROJECT_ROOT"

EXTRACTOR="pollstar/fetch_pollstar.js"
CSV="concerts.csv"

echo "=== Pollstar data refresh ==="

# 1. Prerequisites
if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node is not installed or not on PATH." >&2
  exit 1
fi

if [ ! -f jwt.txt ]; then
  echo "ERROR: jwt.txt not found. Create it with a valid token (README section 3)." >&2
  exit 1
fi

if [ ! -s jwt.txt ]; then
  echo "ERROR: jwt.txt is empty. Paste a valid token into it (README section 3)." >&2
  exit 1
fi

# 2. Handle flags
case "${1:-}" in
  --fresh)
    echo "Removing page cache for a full fresh pull ..."
    rm -rf pages/
    node "$EXTRACTOR"
    ;;
  --csv)
    echo "Rebuilding CSV from cached pages only ..."
    node "$EXTRACTOR" --csv
    ;;
  "")
    node "$EXTRACTOR"
    ;;
  *)
    echo "Unknown option: $1" >&2
    echo "Use one of: (none), --fresh, --csv" >&2
    exit 1
    ;;
esac

# 3. Summary
if [ -f "$CSV" ]; then
  echo ""
  echo "=== Summary ==="
  # Optional summary: record count and eventDate range via a proper CSV reader.
  # Uses only the Python standard library. If python3 is absent, the extractor's own
  # row count above is enough, so we just skip this.
  # (Do not use wc -l: a few fields contain embedded newlines and would inflate the count.)
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import csv, datetime
n = 0
mn = mx = None
with open("concerts.csv") as f:
    for row in csv.DictReader(f):
        n += 1
        try:
            dt = datetime.datetime.strptime(row.get("eventDate", ""), "%m/%d/%Y").date()
        except ValueError:
            continue
        if mn is None or dt < mn: mn = dt
        if mx is None or dt > mx: mx = dt
print(f"concerts.csv records: {n:,}")
print(f"eventDate range:      {mn} to {mx}")
PY
  else
    echo "(python3 not found; skipping the record-count summary)"
  fi
  echo ""
  echo "Done. If you need the shareable split files, run ./pollstar/scripts/split_concerts_csv.sh"
else
  echo "ERROR: concerts.csv was not produced. Check the output above." >&2
  exit 1
fi
