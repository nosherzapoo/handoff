# Pollstar Data Cloud Extractor: Guide

**Author:** Nosher Ali Khan
**Last updated:** 2026-07-02

This repo extracts the Pollstar Data Cloud Boxoffice dataset into a flat CSV. It covers
the extraction only. The downstream analysis scripts are maintained separately and are
not part of this repo. Read this guide once, then use the Quick Start.

---

## 0. Read this first (time sensitive)

The API token in `jwt.txt` is short lived (about 30 days) and is almost certainly expired
by the time you read this. Section 3 tells you how to get a new one. You cannot pull data
until you do.

The token comes from a logged-in **Pollstar Data Cloud** account with an **Ultimate**
subscription. You need working credentials for such an account before anything below
works. Confirm you have that access first.

Note: `jwt.txt` is never committed to this repo (it is a secret and is gitignored). You
create it locally.

---

## 1. What this system does

Pollstar Data Cloud publishes a "Boxoffice" report: one row per concert engagement
(headliner, venue, date, tickets sold, gross, ticket prices, promoter, and more). There
is no export button and no public API. This pipeline:

1. Calls the internal `boxoffice2` API that the website uses.
2. Decrypts the AES-encrypted response.
3. Writes every row (EventDate on or after 2010-01-01) to `concerts.csv`.

Refresh roughly monthly, or whenever you need current numbers.

---

## 2. Prerequisites

Everything runs locally on macOS.

| Tool | Used for | Required? |
| --- | --- | --- |
| Node.js | The extractor (`fetch_pollstar.js`) | Yes |
| `python3` | The optional post-run summary (record count and date range) | Optional |

The extractor uses only Node built-in modules (`https`, `crypto`, `fs`, `path`), so there
is nothing to `npm install`. The summary line printed by `refresh_data.sh` uses only the
Python standard library (`csv`, `datetime`); if `python3` is not present the summary is
skipped and the extractor still prints its own row count.

---

## 3. Refreshing the API token (jwt.txt)

Do this whenever a pull fails with `auth failed (HTTP 401)` or `403`, or about monthly.

1. Log in to Pollstar Data Cloud in a browser (the Ultimate account).
2. Open any Boxoffice / Data Cloud report so data loads.
3. Open browser DevTools, go to the **Network** tab, filter to **Fetch/XHR**.
4. Find a request whose name starts with `boxoffice2?`.
5. Right click it, choose **Copy > Copy as cURL**.
6. In the copied text find the header `Authorization:` and copy its value only (a long
   token, including the word `Bearer` if present).
7. Paste that value into `jwt.txt`, replacing the entire contents. No quotes, no extra
   whitespace (a single trailing newline is fine, the code trims it).

That token is the only secret needed. It is also the AES decryption key source, so nothing
else has to be copied. To sanity check it, run `node fetch_pollstar.js`; a bad token fails
fast on page 0 with an auth error.

---

## 4. Quick Start: pull the data

Once `jwt.txt` holds a valid token, run from the project root:

```bash
./handover/refresh_data.sh
```

It checks prerequisites, runs the extractor, and prints a summary (record count and date
range). Under the hood it runs `node fetch_pollstar.js`, which:

- Fetches page 0 to learn the total row count, then the remaining pages (about 15 pages of
  50,000 rows, roughly 25 seconds per page, 3 at a time).
- Caches each page as `pages/page-N.json`. The run is resumable: if it stops partway, run
  it again and it only fetches the missing pages.
- Rebuilds `concerts.csv` from all cached pages, de-duplicating by `eventId`.

Other modes:

```bash
./handover/refresh_data.sh --csv     # rebuild concerts.csv from cache only, no network
./handover/refresh_data.sh --fresh   # delete the page cache first, then a full pull
```

To make the smaller shareable files (each with a header row):

```bash
./handover/split_concerts_csv.sh     # writes concerts_part1_of_7.csv ... part7_of_7.csv
```

---

## 5. How the extraction works (reference)

You do not need this to run the pipeline, but you need it if Pollstar changes their site
and the extractor breaks. It is all implemented in `fetch_pollstar.js`.

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
r          = Number(s.slice(0, 4))       # a numeric key offset, first 4 chars
ciphertext = s.slice(4)                  # base64
key        = token.substring(r, r + 32)  # 32 chars sliced out of the token itself
plaintext  = AES-256-CBC(base64decode(ciphertext), key, iv = key.slice(0, 16)), PKCS7
```

The decrypted payload is JSON: `{ events: [...], totalRows, totalPages }`.

**If Pollstar changes the scheme:** the decryption logic lives in the site JavaScript.
Saved copies of the relevant bundles are in `chunks/` (look at `523.js`). To find the
current logic, load the site, open the module that fetches `boxoffice2`, and trace how the
response is transformed before the grid renders. The offset-plus-substring-key trick is
the part most likely to change.

---

## 6. File inventory

| Path | Type | Purpose |
| --- | --- | --- |
| `fetch_pollstar.js` | code | The extractor. The heart of the pipeline. |
| `handover/README_HANDOVER.md` | docs | This guide. |
| `handover/refresh_data.sh` | script | Wrapper around the extractor with checks and a summary. |
| `handover/split_concerts_csv.sh` | script | Split `concerts.csv` into shareable parts. |
| `chunks/` | reference | Saved Pollstar site JS. Only needed if the encryption changes. |
| `jwt.txt` | secret | API token. Created locally, gitignored, never committed. |
| `pages/` | cache | One JSON file per API page. Enables resume. Gitignored. |
| `concerts.csv` | output | The full flat dataset, about 166 MB. Gitignored. |
| `concerts_part{1..7}_of_7.csv` | output | Optional shareable splits (each has a header). Gitignored. |

---

## 7. Output schema (concerts.csv)

One row per engagement. 26 columns, in file order:

| Column | Meaning |
| --- | --- |
| `eventId` | Unique engagement id. Used to de-duplicate. |
| `eventDate` | Start date, format M/D/YYYY. |
| `endDate` | End date for multi-night engagements. |
| `numShows` | Number of shows in the engagement. |
| `headLiner` | Main billed act. |
| `support` | Support acts. |
| `ticketsSold` | Total tickets sold across the engagement. |
| `avgTicketsSold` | Tickets sold per show. |
| `grossUSD` | Total gross for the engagement, in US dollars. |
| `avgGrossUSD` | Gross per show, in US dollars. |
| `venueName` | Venue. |
| `companyType` | Venue or promoter company type. |
| `city` | City. |
| `state` | State or region name. |
| `stateAbbrev` | State abbreviation. |
| `country` | Country. |
| `capacity` | Venue capacity for the configuration. |
| `avgCapacitySold` | Percent of capacity sold, 0 to 100 (some bad values above 100 exist). |
| `ticketPriceMin` | Lowest ticket price, already in USD. |
| `ticketPriceMax` | Highest ticket price, already in USD. |
| `ticketPriceAvg` | Average ticket price, already in USD. |
| `currency` | Original reporting currency. Metadata only; prices are already USD. |
| `promoter` | Promoter string, raw. |
| `genre` | Genre. |
| `market` | Market or DMA. |
| `hidden` | Internal flag from Pollstar. |

Prices and gross are already in USD. Verified: `grossUSD / (ticketPriceAvg * ticketsSold)`
equals 1.000 for every currency, so no FX conversion is needed.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `auth failed (HTTP 401)` or `403` | Token expired or wrong. Redo Section 3. |
| `jwt.txt` not found | Create it with a valid token (Section 3). |
| Run stops partway | Network hiccup. Run `./handover/refresh_data.sh` again, it resumes from the `pages/` cache. |
| Row count looks low | Check `pages/` for a truncated page, delete the suspect `page-N.json`, and re-run. |
| Summary line is skipped | `python3` is not installed. The extractor still prints its own row count. Optional. |
| Pollstar changed and decryption fails | See Section 5. Inspect the current site bundle and update `decrypt()` in `fetch_pollstar.js`. |

---

## 9. Security and good practice

- `jwt.txt` is a credential. Do not commit it, paste it into messages, or share the file.
  If it leaks, log in to Pollstar and the old token ages out on its own within about 30 days.
- The dataset is licensed Pollstar content tied to the Ultimate subscription. Share
  derived work per your agreement, not the raw dump. `concerts.csv` and its splits are
  gitignored so they never land in this repo.
- The pipeline is deterministic: same cache in, same CSV out. When in doubt, delete
  `pages/` and pull fresh.

---

## 10. Handover checklist

- [ ] Confirm access to a Pollstar Data Cloud Ultimate account.
- [ ] Create `jwt.txt` with a fresh token (Section 3).
- [ ] Run `./handover/refresh_data.sh` and confirm the row count and date range look current.
- [ ] Skim Section 5 so you can fix the extractor if Pollstar changes their site.

Questions on anything undocumented: start from `fetch_pollstar.js`, which is well commented.
