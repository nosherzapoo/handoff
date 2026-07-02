# Pollstar Data Cloud Extractor

Tooling to extract the Pollstar Data Cloud Boxoffice dataset into a flat CSV.

Pollstar has no export button and no public API. This repo calls the internal
`boxoffice2` API that the website uses, decrypts the AES-encrypted response, and writes
every engagement (EventDate on or after 2010-01-01) to `concerts.csv`.

**Start here:** [`handover/README_HANDOVER.md`](handover/README_HANDOVER.md) is the full
guide (token refresh, how to pull data, how the decryption works, the output schema,
troubleshooting).

## Quick start

```bash
# 1. Put a valid Pollstar bearer token in jwt.txt (see the guide, section 3).
# 2. Pull the data:
./handover/refresh_data.sh
```

## Layout

- `fetch_pollstar.js` - the extractor (Node, standard library only). Pulls and decrypts the API into `concerts.csv`.
- `handover/` - the guide plus helper scripts: `refresh_data.sh` (pull data) and `split_concerts_csv.sh` (split the CSV for sharing).
- `chunks/` - saved Pollstar site JavaScript, kept only as reference for the decryption logic.

## Not in this repo (by design)

The token (`jwt.txt`), the extracted data (`concerts.csv` and its splits), and the page
cache (`pages/`) are excluded via `.gitignore`. The downstream analysis scripts are
maintained separately and are not part of this repo.

Author: Nosher Ali Khan. Last updated: 2026-07-02.
