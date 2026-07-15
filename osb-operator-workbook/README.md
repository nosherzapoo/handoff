# US Operator Time-Series Workbook

Builds a single Excel workbook that tracks the **online sports-betting market share**
of the major US operators — FanDuel, DraftKings, BetMGM, Fanatics, Caesars, ESPN Bet,
and everyone else lumped as "Others" — by **Handle** and **GGR**, month by month, across
the 20 US states that publish operator-level online numbers.

The numbers come **straight from the live OSBdata API** (`https://api.osbdata.com`), which
is the authoritative store fed by the OSBdata scraping pipeline. You do **not** need the
raw state CSVs or the rest of the tracker codebase to build this workbook — one script,
one API, one `.xlsx` out.

> **Start here.** Read section 1 (what you get) and section 3 (how to run). Section 5
> explains the one thing that isn't obvious from the code: *why* it reads from the API
> instead of local files, and the pagination subtlety that keeps it correct.

---

## 1. What you get

Running one command produces **`US_Operator_TimeSeries_Online.xlsx`** — 14 linked sheets:

| Sheet | What it shows |
|---|---|
| **Handle** | $ handle by operator × month, with a % market-share block below. |
| **GGR** | $ gross gaming revenue by operator × month, with % market-share below. |
| **Hold Rate** | GGR ÷ Handle by operator × month (formula-linked to the two sheets above). |
| **Handle YoY (Like-for-Like)** | Y/Y handle growth, *coverage-adjusted* (see section 6). The primary Y/Y view. |
| **GGR YoY (Like-for-Like)** | Y/Y GGR growth, coverage-adjusted. |
| **Quarterly Trends** | Quarterly roll-up: Handle / GGR / Y/Y / Hold by operator, with the still-reporting quarter marked `*`. |
| **Handle Growth YoY** | Simple as-reported Y/Y handle growth (not coverage-adjusted — read the caveat on the sheet). |
| **GGR Growth YoY** | Simple as-reported Y/Y GGR growth. |
| **Handle by State** | Handle pivoted to operator-subtotal + collapsible state rows × month. |
| **GGR by State** | Same, for GGR. |
| **Raw Data** | One row per state × operator-bucket × month — the SUMIFS source every other sheet reads. |
| **Coverage** | Month × state grid: ✓ where a state published that month (so you can see denominator changes). |
| **Sources** | The regulator landing page and report cadence for each state. |
| **Methodology** | Full scope, definitions, and data-quality caveats, embedded in the file itself. |

Every analytical sheet is **formula-driven** (SUMIFS / SUMPRODUCT / INDEX-MATCH pointing at
`Raw Data`), so if you tweak a number in `Raw Data` the whole workbook recomputes on open.

**Two numbers that matter:**
- **Handle** = total dollars wagered.
- **GGR** (Gross Gaming Revenue) = what the operator kept (`handle − payouts`). Can be
  *negative* in a month bettors win net — that's normal, don't "fix" it.
- **Hold** = GGR ÷ Handle.

Current data range: **Jun 2019 → Jun 2026**, 20 states, ~5,000 operator-month rows.

---

## 2. What's in this folder

```
osb-operator-workbook/
├── README.md                        ← you are here (the guide)
├── requirements.txt                 pandas + openpyxl
│
├── build_operator_excel_from_api.py ★ THE entry point — fetch from API, build workbook
├── build_operator_excel.py            the shared workbook builder (all sheet/formula logic)
├── config.py                          STATE_REGISTRY: per-state regulator metadata (Sources sheet)
│
└── US_Operator_TimeSeries_Online.xlsx the generated workbook (committed; regenerate anytime)
```

You only ever *run* `build_operator_excel_from_api.py`. It imports the other two.

---

## 3. How to run it

```bash
# from this folder
pip install -r requirements.txt
python3 build_operator_excel_from_api.py
```

That's it — it fetches ~10k operator rows from the API, aggregates them, and overwrites
`US_Operator_TimeSeries_Online.xlsx` in this folder. Takes ~15–30 seconds (mostly the
paginated fetch).

Options:

```bash
python3 build_operator_excel_from_api.py --out /path/to/output.xlsx   # write elsewhere
python3 build_operator_excel_from_api.py --api-base https://api.osbdata.com  # override API host
```

No API key is needed — the OSBdata read endpoints are public.

---

## 4. How it works, in plain English

```
   api.osbdata.com  (PostgREST over the OSBdata Postgres store)
        │   filter: monthly + online + no sport-split + real operators, for 20 states
        ▼
   ①  fetch_operator_rows()      keyset-paginate every matching row (~10k), in dollars
        │                        apply the same integrity filters as the CSV pipeline
        ▼
   ②  build_operator_excel.build_workbook()
        │   bucket operators → 7 brands, aggregate to state × bucket × month,
        │   write Raw Data, then every analytical sheet as live Excel formulas
        ▼
   US_Operator_TimeSeries_Online.xlsx
```

- **`build_operator_excel_from_api.py`** is the thin data-sourcing layer: it knows how to
  talk to the API and hand a clean DataFrame to the builder.
- **`build_operator_excel.py`** is the heavy lifter: `build_workbook(raw, out_path, values_in_cents)`
  takes a per-operator-month DataFrame and writes the entire 14-sheet workbook. It is
  data-source-agnostic — the same function backs the CSV-based build inside the full
  OSBdata tracker.
- **`config.py`** is pure data (no imports): `STATE_REGISTRY`, the per-state regulator name,
  landing-page URL, and report cadence that populate the **Sources** sheet.

---

## 5. Why the API, and the one correctness subtlety

**Why not read local CSVs?** The full OSBdata tracker writes per-state CSVs, but those can
be stale or missing on any machine whose network blocks certain regulator domains (a known
TLS-proxy issue). The API always reflects what the production pipeline actually loaded, so
it is the authoritative source for a clean-room rebuild like this handoff.

**Units.** The CSV pipeline stores money as integer **cents**; the API serves **dollars**
(the loader divides by 100 on ingest). So this script calls the builder with
`values_in_cents=False` — no conversion. If you ever repoint it at cents-denominated data,
flip that flag.

**Pagination — read this if you touch `fetch_operator_rows()`.** The API is a live table
that the production scrapers **delete-and-reinsert into on a schedule**. If you paginate
with `LIMIT/OFFSET`, an insert mid-fetch shifts the offset window and you silently get
**duplicate or skipped rows** — which then double-count or under-count in the aggregates.
This was observed in practice (a fetch returned 10,756 rows against a true count of 9,800).
The fix, already implemented:

- **Keyset pagination** on the primary key: `order=id.asc` + `id=gt.<last_id>` per page.
  Stable under concurrent inserts — no drifting window.
- A **defensive dedup on `id`** after fetching, in case a scrape straddles the run.

If you change the fetch, keep both guards.

---

## 6. Scope & methodology (the short version)

The workbook's **Methodology** sheet is the authoritative, full version — it ships inside
the file. The essentials:

- **Scope:** online channel only; retail and combined excluded. All time since each state's
  online launch.
- **20 states included:** AZ, CT, DC, IA, IL, IN, KS, KY, MA, MD, ME, MI, MO, NH, NY, OH,
  OR, PA, WV, WY. (NJ is deliberately excluded — it publishes operator GGR but not operator
  handle, so hold can't be computed per operator.)
- **Buckets (fixed):** FanDuel, DraftKings, BetMGM, Fanatics, Caesars, ESPN Bet, Others.
  Barstool history is already merged into ESPN Bet upstream.
- **Integrity rule:** every operator-month row must have **both** a positive handle **and**
  a GGR value, or it's dropped — otherwise hold-rate aggregates would mix a numerator from
  one row-set with a denominator from another.
- **GGR fallback:** where the normalized `standard_ggr` is null but the regulator-published
  `gross_revenue` exists (MA, MI, OH, KS, NH), the latter is coalesced in — it's the same
  published number.
- **Like-for-Like Y/Y** (the primary Y/Y): numerator = *all* states reporting the current
  month; denominator = *those same states* a year earlier. A state lagging this year is
  dropped from both sides (removes coverage-lag distortion); a genuinely new state stays in
  the numerator and contributes 0 to the denominator, so real market expansion still shows.
- **Known data-quality notes** (also on the Methodology sheet): WV reports online books under
  casino-skin venue names, so all WV rows fall into "Others"; IL operator GGR is sparse
  before mid-2023; MO online launched Dec 2025 (few months of data); KY 2025+ comes from the
  KHRC Tableau dashboard via OCR.

---

## 7. Relationship to the full OSBdata tracker

This folder is a **standalone extract** of two files from the main OSBdata tracker
(`scripts/build_operator_excel.py` and `scripts/build_operator_excel_from_api.py`) plus a
copy of `scrapers/config.py`, wired to run without the rest of that codebase. Inside the
tracker, the same `build_workbook()` also has a CSV-sourced entry point
(`build_operator_excel.py`'s own `main()`), which needs the tracker's `data/processed/*.csv`
tree and is **not** shipped here. For this handoff, the API builder is the only path you
need.

---

Author: Nosher Ali Khan. Last updated: 2026-07-15.
