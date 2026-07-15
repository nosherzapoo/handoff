# Weekly Prediction-Market Notional Volume Workbook

A single self-contained script that turns the live Dune query
**"Weekly Prediction Market Notional Volume"**
([dune.com/queries/5753743](https://dune.com/queries/5753743)) into the
`Weekly PM Notional Value.xlsx` workbook — the same two-sheet exhibit shipped
each week (a `raw` data sheet and a formula-driven `pivot`).

> **Start here.** This README is the whole map. The one non-obvious piece is in
> section 4: *why the scrape needs a real browser.* Everything else is just
> "run the script."

---

## 1. What it does, in plain English

```
   Dune query 5753743  (JS-rendered, behind Cloudflare, no API key)
                          │
                          ▼
   ①  scrape_dune()          drive a real Chrome, page through the results
                          │   table, write every row → dune_5753743.csv
                          ▼
   ②  build_workbook()       raw sheet + pivot sheet (SUMIFS) → the .xlsx
                          │
                          ▼
   Weekly PM Notional Value.xlsx
```

Both steps live in one file, `build_pm_notional_workbook.py`. One command does
the whole thing:

```bash
python3 build_pm_notional_workbook.py
```

**What each column means**

- **week** — the Monday-anchored week bucket (a date).
- **platform** — the venue: Kalshi, Polymarket, Opinion, Polymarket (US),
  Limitless, Crypto.com, Predict, Other, Hyperliquid (whatever the query
  returns that week).
- **Notional USD Volume** — dollars of notional traded on that venue that week.

---

## 2. Quick start

```bash
pip install -r requirements.txt
playwright install chrome        # one-time: gets a real Chrome for the scrape

# Full run — scrape Dune, then build the workbook:
python3 build_pm_notional_workbook.py

# Result:
#   dune_5753743.csv               the scraped raw data (cache)
#   Weekly PM Notional Value.xlsx  the deliverable
```

Rebuild the workbook **without a browser** from data you already scraped:

```bash
python3 build_pm_notional_workbook.py --from-csv dune_5753743.csv
```

Name the output the way the weekly file is dated:

```bash
python3 build_pm_notional_workbook.py --out "Weekly PM Notional Value (8th July).xlsx"
```

**All flags**

| Flag              | Meaning                                                             |
| ----------------- | ------------------------------------------------------------------- |
| `--from-csv PATH` | Skip the scrape; build from an already-scraped CSV (no browser).    |
| `--csv PATH`      | Where to write/read the scraped CSV (default `dune_5753743.csv`).   |
| `--out PATH`      | Output workbook path (default `Weekly PM Notional Value.xlsx`).     |
| `--headless`      | Run Chrome headless during the scrape (Cloudflare may flag it).     |
| `--no-build`      | Only scrape to CSV; don't build the workbook.                       |

---

## 3. What's in the workbook

**`raw`** — one row per `(week, platform)`, sorted by week ascending then
platform alphabetically (exactly the order Dune returns). Header bold, top row
frozen, notional formatted `#,##0.00`, weeks formatted `yyyy-mm-dd`.

**`pivot`** — platforms down the rows, weeks across the columns.

- **Row order** is by total notional, descending (largest venue on top).
- Every cell is a live `=SUMIFS(...)` against the `raw` sheet, so if you edit
  `raw` by hand the pivot updates itself — same as the hand-built original.
- A **Total** column (right) sums each platform across all weeks, a **Total**
  row (bottom) sums each week across all platforms, and the corner cell is the
  grand total.

This reproduces the reference file `Weekly PM Notional Value (8th July).xlsx`
cell-for-cell: identical `raw` values, identical `pivot` formulas, identical
number formats, fonts, and frozen panes. (Verified by diffing every cell.)

---

## 4. Why the scrape needs a real browser (the one non-obvious part)

Dune renders its results in JavaScript behind Cloudflare. Every shortcut fails:

- **WebFetch / requests** → returns the empty loading skeleton, no data.
- **`curl` on `/csv`** → returns a Cloudflare challenge page, not CSV.
- **`api.dune.com`** → needs a **paid API key** (none is set here).

So the only key-free path is to drive a **real Chrome** with Playwright, let it
solve the Cloudflare challenge, and read the numbers off the rendered page. The
script does this the same way every time; the details that make it reliable:

1. **Persistent Chrome profile** at `/tmp/dune_profile`. The Cloudflare
   clearance cookie is cached there, so the *first* run may sit on the challenge
   for ~20-30 s but later runs clear it in a couple of seconds.
2. **`channel="chrome"`** (the real Chrome, not bundled Chromium) +
   `playwright-stealth` + `--disable-blink-features=AutomationControlled` — this
   combination is what actually gets past the challenge.
3. **Stale-cache handling.** If the query hasn't been viewed in a while Dune
   shows no table until you re-run it; the script clicks the Run / freshness
   control and waits (up to 8 min) for results to render.
4. **Pagination by page-number input.** The "Next" button is unreliable, so the
   script types into the page-number box (using React's value setter + an Enter
   keydown) and waits for the first row to change before reading each page. Dune
   shows 25 rows/page; the total comes from the "N rows" footer.

If Cloudflare ever gets stubborn: delete `/tmp/dune_profile` and run again with
a visible window (the default — don't pass `--headless`), so you can solve any
challenge by hand once; the cookie then persists for subsequent runs.

**Don't want to deal with the browser at all?** If you already have a
`dune_5753743.csv` (e.g. from a previous run, or exported from Dune manually),
`--from-csv` rebuilds the workbook offline with only `openpyxl` installed.

---

## 5. Files in this folder

```
pm-notional-workbook/
├── README.md                        ← you are here
├── build_pm_notional_workbook.py    ★ the scraper + workbook builder (one file)
├── requirements.txt                 Python dependencies
├── dune_5753743.csv                 last scraped data (cache; regenerated)
└── Weekly PM Notional Value.xlsx     the generated workbook (the deliverable)
```

The `.xlsx` and `.csv` are regenerated by running the script; the committed
copies are the most recent build so the deliverable is available without a
scrape.

---

## 6. Refreshing next week

The Dune query updates itself. To produce next week's file, just re-run:

```bash
python3 build_pm_notional_workbook.py --out "Weekly PM Notional Value (Nth Month).xlsx"
```

New weeks appear as extra columns in `pivot`; a brand-new venue appears as an
extra `raw` platform and a new `pivot` row, slotted into the total-descending
order automatically. Nothing to configure.

---

Author: Nosher Ali Khan. Source query: Dune 5753743
("Weekly Prediction Market Notional Volume").
