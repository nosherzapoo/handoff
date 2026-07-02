# Pollstar Data Cloud Pipeline

Internal tooling to extract the Pollstar Data Cloud Boxoffice dataset and build a set of
concert-market analyses on top of it.

**Start here:** [`handover/README_HANDOVER.md`](handover/README_HANDOVER.md) is the full
maintenance guide (token refresh, how to pull data, the analyses, data dictionary,
troubleshooting, and a handover checklist).

## Layout

- `fetch_pollstar.js` - the extractor (Node). Pulls and decrypts the Boxoffice API into `concerts.csv`.
- `handover/` - the maintenance guide plus helper scripts (`refresh_data.sh`, `run_analyses.sh`, `split_concerts_csv.sh`, `refresh_cpi.sh`) and `requirements.txt`.
- `*.py` - analysis scripts that turn `concerts.csv` and the page cache into Excel workbooks.
- `chunks/` - saved Pollstar site JavaScript, kept only as reference for the decryption logic.
- `cpi_u_cpiaucsl.csv` - CPI-U deflator series from FRED.

## Not in this repo (by design)

The token (`jwt.txt`), the licensed raw data (`concerts.csv` and its splits), the page
cache (`pages/`), the Python virtual environment (`.venv/`), and the generated workbooks
and charts are excluded via `.gitignore`. Regenerate them by following the handover guide.

Author: Nosher Ali Khan. Last updated: 2026-07-02.
