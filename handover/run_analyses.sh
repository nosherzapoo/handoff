#!/usr/bin/env bash
#
# run_analyses.sh
# Regenerate every analysis workbook and its charts from the local data.
# Reads concerts.csv and pages/. Does not touch the network (except optional CPI refresh).
#
# Author: Nosher Ali Khan
# Last updated: 2026-07-02
#
# Usage (run from the project root):
#   ./handover/run_analyses.sh              # rebuild all workbooks
#   ./handover/run_analyses.sh --with-cpi   # also refresh the CPI-U deflator file first
#
# See README_HANDOVER.md section 6.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"   # scripts live in handover/, data lives one level up
cd "$PROJECT_ROOT"

PY=".venv/bin/python"

# Prerequisites
if [ ! -x "$PY" ]; then
  echo "ERROR: $PY not found. Rebuild the venv (README section 2)." >&2
  exit 1
fi
if [ ! -f concerts.csv ]; then
  echo "ERROR: concerts.csv missing. Run ./handover/refresh_data.sh first." >&2
  exit 1
fi

# Optional: refresh the CPI-U deflator from FRED
if [ "${1:-}" = "--with-cpi" ]; then
  echo "Refreshing CPI-U (CPIAUCSL) from FRED ..."
  curl -sL "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&cosd=2018-10-01&coed=$(date +%Y-%m-%d)" -o cpi_u_cpiaucsl.csv
  echo "  saved cpi_u_cpiaucsl.csv"
fi

run () {
  echo ""
  echo "=== Running $1 ==="
  "$PY" "$1"
}

# Order does not matter; each script is independent.
run build_excel.py                 # -> Pollstar_US_Promoter_Analysis.xlsx
run ticket_price_analysis.py       # -> Ticket_Price_Analysis.xlsx + PNGs
run build_excel_full.py            # -> US_Quarterly_Ticket_Price_Spread.xlsx + PNGs
run premium_ip_persistence.py      # -> Premium_IP_Persistence.xlsx + PNGs

echo ""
echo "=== All analyses rebuilt. Workbooks are in $PROJECT_ROOT ==="
