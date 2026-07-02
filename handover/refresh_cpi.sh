#!/usr/bin/env bash
#
# refresh_cpi.sh
# Download the latest CPI-U deflator series (CPIAUCSL, seasonally adjusted) from FRED.
# Used by build_excel_full.py to convert prices to constant 2025 USD.
#
# Author: Nosher Ali Khan
# Last updated: 2026-07-02
#
# Usage (run from the project root):
#   ./handover/refresh_cpi.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"   # scripts live in handover/, data lives one level up
cd "$PROJECT_ROOT"

OUT="cpi_u_cpiaucsl.csv"
URL="https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&cosd=2018-10-01&coed=$(date +%Y-%m-%d)"

echo "Downloading CPI-U (CPIAUCSL) from FRED ..."
curl -fsSL "$URL" -o "$OUT"
echo "Saved $OUT"
echo ""
echo "Note: the analysis interpolates any single missing month automatically."
echo "Last few rows:"
tail -n 5 "$OUT"
