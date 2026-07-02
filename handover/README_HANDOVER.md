# Pollstar Data Cloud Pipeline: Handover Guide

**Author:** Nosher Ali Khan
**Last updated:** 2026-07-02
**Project directory:** `/Users/nosherzapoo/Desktop/claude/pollstar`

This document is the single source of truth for maintaining the Pollstar concert
dataset and the analyses built on top of it. Read the whole thing once, then use
the Quick Start for the recurring task.

**Where things live.** This guide and the helper scripts sit in the `handover/`
subfolder. The data, the extractor (`fetch_pollstar.js`), and the analysis scripts sit
in the project root one level up. Run all commands below from the project root, using
the `./handover/` prefix shown (each script targets the project root automatically, so
it does not matter which directory you are actually standing in).

---

## 0. Read this first (time sensitive)

The API token in `jwt.txt` **expires 2026-07-03 14:21 UTC**. It is almost certainly
expired by the time you read this, which is normal. Section 3 tells you how to get a
new one. You cannot pull fresh data until you do this.

The token comes from a logged-in **Pollstar Data Cloud** account with an **Ultimate**
subscription. The account used so far is `ian.moore@bernsteinsg.com`. You need working
login credentials for that account, or your own Ultimate subscription, before anything
below will work. Confirm you have this access on day one.

---

## 1. What this system does

Pollstar Data Cloud publishes a "Boxoffice" report: one row per concert engagement
(headliner, venue, date, tickets sold, gross, ticket prices, promoter, and more).
There is no export button and no public API. This pipeline:

1. Calls the internal `boxoffice2` API that the website uses.
2. Decrypts the AES-encrypted response.
3. Writes every row (EventDate on or after 2010-01-01) to a flat file, `concerts.csv`.
4. Feeds that file into a set of analysis scripts that produce Excel workbooks.

The recurring job is step 1 to 3: refresh the data roughly monthly, or whenever an
analysis needs current numbers. Steps for the analyses are in Section 6.

---

## 2. Prerequisites and environment

Everything runs locally on macOS. Two runtimes are involved.

| Tool | Used for | Version confirmed working |
| --- | --- | --- |
| Node.js | Data extraction (`fetch_pollstar.js`) | v23.6.0 |
| Python (project venv) | Analyses and charts | 3.13.1 |

The Python environment is a virtual environment at `.venv/` in the project root. It
already has the packages listed in `handover/requirements.txt` (pandas, numpy,
matplotlib, openpyxl). Always call it explicitly as `.venv/bin/python`, never the system
`python3`.

Do not use Homebrew `python3` or `pip3` directly. Homebrew Python is externally managed
(PEP 668) and `pip install` will fail. If you ever need to rebuild the venv:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r handover/requirements.txt
```

The Node script uses only built-in modules (`https`, `crypto`, `fs`, `path`), so there
is nothing to `npm install`.

---

## 3. Refreshing the API token (jwt.txt)

Do this whenever a data pull fails with `auth failed (HTTP 401)` or `HTTP 403`, or
roughly once a month. Tokens last about 30 days.

1. Log in to Pollstar Data Cloud in a browser (the Ultimate account).
2. Open any Boxoffice / Data Cloud report so data loads.
3. Open browser DevTools, go to the **Network** tab, filter to **Fetch/XHR**.
4. Find a request whose name starts with `boxoffice2?`.
5. Right click it, choose **Copy > Copy as cURL**.
6. In the copied text find the header `Authorization:` (or `authorization:`). Copy its
   value only. It is a long token. It may or may not start with the word `Bearer`.
   Copy exactly what follows `Authorization: ` including `Bearer ` if present.
7. Paste that value into `jwt.txt`, replacing the entire contents. No quotes, no extra
   whitespace, no trailing newline issues (a single trailing newline is fine, the code
   trims it).

That token is the only secret needed. The same token is also the AES decryption key
source, so nothing else has to be copied.

To sanity check the token before a full run:

```bash
node fetch_pollstar.js   # if the token is bad it fails fast on page 0 with an auth error
```

---

## 4. Quick Start: refresh the data

Once `jwt.txt` holds a valid token:

```bash
cd /Users/nosherzapoo/Desktop/claude/pollstar
./handover/refresh_data.sh
```

`refresh_data.sh` checks your prerequisites, runs the extractor, and prints a summary
(row count and date range). Under the hood it runs `node fetch_pollstar.js`, which:

- Fetches page 0 to learn the total row count, then the remaining pages (about 15 pages
  of 50,000 rows, roughly 25 seconds per page, 3 at a time).
- Caches each page as `pages/page-N.json`. The run is resumable: if it stops partway,
  run it again and it only fetches the missing pages.
- Rebuilds `concerts.csv` from all cached pages, de-duplicating by `eventId`.

To rebuild `concerts.csv` from the cache without hitting the network:

```bash
node fetch_pollstar.js --csv
```

To force a completely fresh pull, delete the cache first:

```bash
rm -rf pages/ && ./handover/refresh_data.sh
```

After refreshing, if you need the smaller shareable files (see Section 7), run
`./handover/split_concerts_csv.sh`.

---

## 5. How the extraction works (reference)

You do not need this to run the pipeline, but you need it if Pollstar changes their
site and the script breaks. It is all implemented in `fetch_pollstar.js`.

**Endpoint**

```
GET https://data.pollstar.com/data/v1/research/datacloud/boxoffice2
    ?filter=EventDate>=2010-01-01
    &page=<0-indexed>
    &pageSize=50000
    &boxOfficeOnly=true
    &festivals=0
    &sortColumn=eventDate
    &sortAscending=false
```

Auth is the `Authorization: <token>` header. It is not a cookie and there is no API key.

**Response decryption** (reverse engineered from the site bundle, chunk `523`, module
`56382`). The response body is a JSON-encoded string `s`. Then:

```
r          = Number(s.slice(0, 4))     # a numeric key offset, first 4 chars
ciphertext = s.slice(4)                # base64
key        = token.substring(r, r + 32)  # 32 chars sliced out of the token itself
plaintext  = AES-256-CBC(base64decode(ciphertext), key, iv = key.slice(0, 16)), PKCS7
```

The decrypted payload is JSON: `{ events: [...], totalRows, totalPages }`.

**If Pollstar changes the scheme:** the decryption logic lives in the site JavaScript.
Saved copies of the relevant bundles are in `chunks/` (look at `523.js`). To find the
current logic, load the site, open the module that fetches `boxoffice2`, and trace how
the response is transformed before the grid renders. The offset-plus-substring-key trick
is the part most likely to change.

---

## 6. The analyses (deliverables)

All analysis scripts read local files only (no network) and write an Excel workbook plus
PNG charts into the project root. Regenerate everything at once with:

```bash
./handover/run_analyses.sh
```

Or run any one individually with `.venv/bin/python <script>`. Details:

| Script | Reads | Produces | What it shows |
| --- | --- | --- | --- |
| `build_excel.py` (with `promoter_map.py`) | `pages/*.json` | `Pollstar_US_Promoter_Analysis.xlsx` | US promoter market share by parent company and segment |
| `ticket_price_analysis.py` | `pages/*.json` | `Ticket_Price_Analysis.xlsx`, `ticket_price_{us,europe,all}.png` | Mean min and max ticket price by year, superstar vs non-superstar |
| `build_excel_full.py` | `concerts.csv`, `cpi_u_cpiaucsl.csv` | `US_Quarterly_Ticket_Price_Spread.xlsx` and 6 PNGs | Quarterly weighted prices and max/min spread, gross tiers, concentration, top-1% artist spread |
| `premium_ip_persistence.py` | `concerts.csv` | `Premium_IP_Persistence.xlsx`, `persistence.png`, `replenishment.png` | Durability and replenishment of top-1% headliners |

Notes:

- `build_excel.py` and `ticket_price_analysis.py` read the cached `pages/*.json`, not
  `concerts.csv`. If you refresh the data, the `pages/` cache is refreshed too, so they
  stay in sync. Just do not delete `pages/` and keep only the CSV.
- `quarterly_price_analysis.py` is an **older, superseded** version of the quarterly
  price work. `build_excel_full.py` replaces it (it rebuilds the whole workbook fresh,
  which avoids losing embedded chart images). Keep `quarterly_price_analysis.py` for
  reference only, do not run it as part of the pipeline.
- Each workbook has a `README` sheet documenting its own methodology. Read that sheet
  before interpreting numbers.

### CPI deflation data

`build_excel_full.py` deflates prices to constant 2025 US dollars using CPI-U (series
`CPIAUCSL`, seasonally adjusted, from FRED), stored in `cpi_u_cpiaucsl.csv`. To update
it (for example when extending past 2025), refresh the file:

```bash
./handover/refresh_cpi.sh          # convenience wrapper, or the raw curl below
curl -sL "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&cosd=2018-10-01&coed=$(date +%Y-%m-%d)" -o cpi_u_cpiaucsl.csv
```

You can also refresh the CPI file as part of the analyses run with
`./handover/run_analyses.sh --with-cpi`.

One quirk: the source had a missing value for October 2025 (a data gap). The analysis
script interpolates any single missing month from its neighbors, so a small gap is
handled automatically. If a longer gap appears, note it in the workbook.

---

## 7. File inventory

Kept and meaningful:

| Path | Type | Keep? | Purpose |
| --- | --- | --- | --- |
| `handover/` | docs | yes | This guide plus the helper scripts (`refresh_data.sh`, `run_analyses.sh`, `split_concerts_csv.sh`, `refresh_cpi.sh`) and `requirements.txt`. |
| `.gitignore` | config | yes | Kept at the project root (git reads it there). Excludes the secret, the venv, big CSVs, and outputs. |
| `fetch_pollstar.js` | code | yes | The extractor. The heart of the pipeline. |
| `jwt.txt` | secret | yes | API token. Refresh monthly. Never commit or share. |
| `pages/` | cache | yes | One JSON file per API page. Enables resume and feeds two analyses. |
| `concerts.csv` | data | yes | The full flat dataset, about 166 MB, 728k+ rows. |
| `concerts_part{1..7}_of_7.csv` | data | optional | The full CSV split into 7 smaller files for sharing (each has a header). Regenerate with `handover/split_concerts_csv.sh`. |
| `cpi_u_cpiaucsl.csv` | data | yes | CPI-U deflator series from FRED. |
| `promoter_map.py` | code | yes | Promoter name normalization, used by `build_excel.py`. |
| `build_excel.py` | code | yes | Promoter analysis. |
| `ticket_price_analysis.py` | code | yes | Superstar vs non-superstar price analysis. |
| `build_excel_full.py` | code | yes | Quarterly price, spread, tiers, concentration, top-1% artist workbook. |
| `premium_ip_persistence.py` | code | yes | Persistence and replenishment workbook. |
| `quarterly_price_analysis.py` | code | reference | Superseded by `build_excel_full.py`. Do not run. |
| `*.xlsx` | output | yes | The delivered workbooks. Regenerated by the scripts. |
| `*.png` | output | yes | Chart images embedded in the workbooks. Regenerated by the scripts. |
| `chunks/` | reference | yes | Saved copies of the Pollstar site JS. Only needed if the encryption changes. |
| `.venv/` | env | yes | Python virtual environment. Do not commit. |

Can be deleted safely (leftovers, not used by anything):

| Path | Why it is safe to remove |
| --- | --- |
| `Pollstar Data Cloud _ Boxoffice.html` | A saved copy of the site shell. Contains no data (data loads at runtime from the API). |
| `Pollstar Data Cloud _ Boxoffice_files/` | Supporting assets for that saved page. |
| `__pycache__/` | Python bytecode cache, regenerated automatically. |
| `.DS_Store` | macOS Finder metadata. |

---

## 8. Data dictionary (concerts.csv)

One row per engagement. 26 columns, in file order:

| Column | Meaning |
| --- | --- |
| `eventId` | Unique engagement id. Used to de-duplicate. |
| `eventDate` | Start date, format M/D/YYYY. |
| `endDate` | End date for multi-night engagements. |
| `numShows` | Number of shows in the engagement. |
| `headLiner` | Main billed act. Aggregate on this for artist-level work. |
| `support` | Support acts. |
| `ticketsSold` | Total tickets sold across the engagement. Use as attendance weight. |
| `avgTicketsSold` | Tickets sold per show. |
| `grossUSD` | Total gross for the engagement, in US dollars. |
| `avgGrossUSD` | Gross per show, in US dollars. |
| `venueName` | Venue. |
| `companyType` | Venue or promoter company type. |
| `city` | City. |
| `state` | State or region name. |
| `stateAbbrev` | State abbreviation. |
| `country` | Country. `United States` for US scope. |
| `capacity` | Venue capacity for the configuration. |
| `avgCapacitySold` | Percent of capacity sold, 0 to 100. Has some bad values above 100 (cap at 100). |
| `ticketPriceMin` | Lowest ticket price (get-in), already in USD. |
| `ticketPriceMax` | Highest ticket price, already in USD. |
| `ticketPriceAvg` | Average ticket price, already in USD. |
| `currency` | Original reporting currency. Metadata only, prices are already converted to USD. |
| `promoter` | Promoter string, raw. Normalize with `promoter_map.classify`. |
| `genre` | Genre. |
| `market` | Market or DMA. |
| `hidden` | Internal flag from Pollstar. |

---

## 9. Analysis conventions (agreed with the client)

These conventions are baked into the scripts. Keep them consistent across future work.

- **Currency:** all price and gross fields are already in USD. The `currency` column is
  only the original reporting currency. Verified: `grossUSD / (ticketPriceAvg *
  ticketsSold)` equals 1.000 for every currency. No FX conversion is needed.
- **Real vs nominal:** for real-terms trends, deflate with CPI-U to constant 2025 USD
  using `cpi_u_cpiaucsl.csv`. Ratios (like max divided by min) are unit free and do not
  need deflation.
- **Outliers:** `ticketPriceMax` contains data-entry errors (for example a gross typed
  into a price field, up to millions). Winsorize price fields to the 0.1 and 99.9
  percentiles before averaging. `avgCapacitySold` has values above 100 percent, cap at 100.
- **Attendance weighting:** for market-level price trends, weight by `ticketsSold` so
  large shows count more, rather than a simple average across engagements.
- **Thin samples:** 2020 and 2021 are COVID years with very few shows. Flag or suppress
  thin cells (the scripts use thresholds such as fewer than 2000 events in a quarter, or
  fewer than 25 shows in a cell) and shade COVID periods on charts.
- **Superstar definition (older price analysis):** a headliner whose average gross per
  show over 2010 to 2025 is at least 1,000,000 USD with at least 3 engagements.
- **Top 1 percent (newer analyses):** the top 1 percent of headliners by gross, ranked
  within each year.
- **Regions:** US is `country == "United States"`. Europe is a fixed list of about 31
  countries including the UK (see `ticket_price_analysis.py`). All is worldwide.

---

## 10. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `auth failed (HTTP 401)` or `403` | Token expired or wrong. Redo Section 3. |
| `FAILED: ... jwt.txt` not found | `jwt.txt` is missing. Create it with a valid token. |
| Node run stops partway | Network hiccup. Just run `./handover/refresh_data.sh` again, it resumes from the `pages/` cache. |
| Row count looks low or wrong | Check `pages/` for a truncated page, delete the suspect `page-N.json`, and re-run. |
| `ModuleNotFoundError` in Python | You used system Python. Use `.venv/bin/python`, or rebuild the venv (Section 2). |
| Chart images missing from a workbook | Do not load and re-save a workbook with openpyxl (it drops images). Regenerate from the script, which builds fresh. |
| CPI file has a blank month | The script interpolates a single missing month. For a longer gap, refresh the CPI file (Section 6). |
| Pollstar changed and decryption fails | See Section 5. Inspect the current site bundle and update `decrypt()` in `fetch_pollstar.js`. |

---

## 11. Security and good practice

- `jwt.txt` is a credential. Do not commit it to version control, paste it into
  messages, or share the file. If it leaks, log in to Pollstar and the old token ages
  out on its own within about 30 days.
- The dataset is licensed Pollstar content tied to the Ultimate subscription. Share
  derived analyses per your agreement, not the raw dump.
- `concerts.csv` is large (166 MB). If you set up git here, use the provided
  `.gitignore` so the CSV, the split parts, `jwt.txt`, and `.venv/` stay out of the repo.
- The pipeline is deterministic: same cache in, same CSV out. When in doubt, delete
  `pages/` and pull fresh.

---

## 12. Handover checklist

- [ ] Confirm access to the Pollstar Data Cloud Ultimate account.
- [ ] Refresh `jwt.txt` with a fresh token (Section 3).
- [ ] Run `./handover/refresh_data.sh` and confirm the row count and date range look current.
- [ ] Run `./handover/run_analyses.sh` and open each workbook to confirm charts render.
- [ ] Read the `README` sheet inside each workbook.
- [ ] Skim the memory-of-decisions in Section 9 so future cuts stay consistent.

Questions on anything undocumented: start from `fetch_pollstar.js` (well commented) and
the per-workbook `README` sheets. Good luck.
