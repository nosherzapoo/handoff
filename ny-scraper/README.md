# NY Sports-Betting Scraper

Automated pipeline that tracks New York's online sports-betting market. Every run it
pulls the latest weekly reports the **NY State Gaming Commission** publishes for all
9 licensed operators, extracts the numbers, builds a formatted exhibit, notices what
changed since last time, and emails an update with the spreadsheets attached.

> **Start here.** This README is the whole map. Read the *"How it's triggered"* section
> before anything else — it explains the one piece that isn't obvious from the code.

---

## 1. What it does, in plain English

```
   NY Gaming Commission website (9 operators, each publishes a PDF + an Excel)
                          │
                          ▼
   ①  download_reports.py        grab every operator's PDF and Excel (in parallel)
                          │
                          ▼
   ②  extract_to_csv_v2.py       read Handle + GGR per week → ny_gaming_data.csv
                          │
                          ▼
   ③  create_weekly_exhibit.py   build the pretty 5-week exhibit (.xlsx)
                          │
                          ▼
   ④  compare_data.py            diff vs last run, email the update, save a snapshot
                          │
                          ▼
   GitHub Action then commits the refreshed data back to the repo
```

Run in order, the four scripts take you from "raw government website" to "email in your
inbox." Each one only reads the file the previous one wrote, so the order matters.

**The 9 operators tracked:** Bally Bet, BetMGM, Caesars, DraftKings, ESPN Bet (Wynn),
Fanatics, FanDuel, Resorts World, Rush Street.

**The two numbers that matter:**
- **Handle** = total dollars wagered that week.
- **GGR** (Gross Gaming Revenue) = what the operator kept (can be *negative* in a week
  where bettors win net — this is normal, don't "fix" it).
- **Hold** = GGR ÷ Handle, computed in the exhibit.

---

## 2. What's in this folder

```
ny-scraper/
├── README.md                       ← you are here (the guide)
├── requirements.txt                Python dependencies
│
├── download_reports.py             ① download PDFs + Excels from the state site
├── extract_to_csv_v2.py            ② parse them into ny_gaming_data.csv
├── create_weekly_exhibit.py        ③ build the formatted weekly exhibit .xlsx
├── compare_data.py                 ④ detect changes + send the email
│
├── .github/workflows/
│   ├── ny-gaming-monitor.yml       the automated run (the recurring emails)
│   └── ny-gaming-manual.yml        on-demand run to a chosen email address
│
├── docs/
│   ├── setup_github_secrets.md     how to wire up the email (SMTP) secrets — DO THIS FIRST
│   └── setup_public_form.md        optional: the "enter-your-email" web form
│
└── web/                            optional public request form (not required to run)
    ├── index.html                  the form page
    ├── cloudflare_worker.js        backend option A (Cloudflare)
    └── api/trigger.js              backend option B (Vercel)
```

Only **code and docs** are tracked here (same convention as the rest of the `handoff`
repo). The data files the pipeline produces — `ny_gaming_data.csv`, the `.xlsx` outputs,
the downloaded `NY_State_Reports_*/` folders, and `data_archive/` — are **generated**, so
they're gitignored. You get them by running the pipeline, not from git.

---

## 3. ⚠️ How it's triggered (the one non-obvious thing)

**There is no `schedule:` / cron block in the GitHub workflows.** Look at
`.github/workflows/ny-gaming-monitor.yml` — its only trigger is `workflow_dispatch`
(i.e. "run when something calls the API"). So GitHub itself does **not** run this on a
timer.

Instead, an **external scheduler (cron-job.org)** calls the GitHub "dispatch this
workflow" API endpoint on a schedule. That external job is what makes the emails show up
every ~10 minutes. **It lives outside this repo**, in a cron-job.org account.

> 🔑 **If the emails ever stop, check cron-job.org first — not the code.** The most likely
> cause is the external trigger being paused, or its GitHub token expiring. You will need
> access to that cron-job.org account to see or change the cadence.

The intended cadence (configured in cron-job.org) is:
- **Thursday:** every 2 hours
- **Friday 4 AM–noon:** every 15 minutes (this is when new data usually lands)
- **Friday 1 PM–11 PM:** every hour

You can trigger a run yourself any time from the repo's **Actions** tab → *Run workflow*.

---

## 4. Deploy it from scratch (≈10 minutes)

The pipeline currently lives in the live repo **`github.com/nosherzapoo/OSBdata`**. To
stand up your own copy:

1. **Create a repo** and copy *everything in this folder* to its root. The scripts and
   `.github/workflows/` are already laid out to run from the repo root as-is.
2. **Add the email secrets** — follow [`docs/setup_github_secrets.md`](docs/setup_github_secrets.md).
   You need `EMAIL_USER`, `EMAIL_PASS` (a Gmail *App Password*, not the login password),
   `SMTP_SERVER`, `SMTP_PORT`, and `NOTIFICATION_EMAIL1/2/3` (the recipients).
3. **Enable Actions** on the repo, then open the **Actions** tab and click
   *Run workflow* on *NY Gaming Data Monitor* to confirm you get an email.
4. **Set up the recurring trigger.** Either:
   - point a **cron-job.org** job at the GitHub dispatch API (how it runs today — keeps
     the fine-grained schedule above), **or**
   - simpler: add a `schedule:` cron block to `ny-gaming-monitor.yml` so GitHub runs it
     directly (coarser, and GitHub cron can lag a few minutes, but no external service to
     babysit).

---

## 5. Run it locally

```bash
pip install -r requirements.txt

python download_reports.py        # ① downloads into NY_State_Reports_<today>/
python extract_to_csv_v2.py       # ② writes ny_gaming_data.csv
python create_weekly_exhibit.py   # ③ writes ny_gaming_weekly_exhibit.xlsx

# ④ compare + email. Set these env vars first, or it just prints and skips the email:
EMAIL_USER=you@gmail.com EMAIL_PASS='app password' \
SMTP_SERVER=smtp.gmail.com SMTP_PORT=587 \
NOTIFICATION_EMAIL=you@gmail.com FORCE_SEND=true \
python compare_data.py
```

Always run the scripts **from the same directory** — each reads the file the previous one
wrote in the current folder.

- `FORCE_SEND=true` sends the email even when nothing changed (used by the manual run).
- Leave the email vars unset to test steps ①–③ without sending anything.

---

## 6. The one piece of business logic to preserve

Each operator publishes the **same weekly figures in two formats — a PDF and an Excel —
but not always at the same time.** Sometimes a new week appears on the PDF first, sometimes
on the Excel first. `extract_to_csv_v2.py` handles this so no week is ever missed:

- **PDF is preferred** — its value wins for any week it reports.
- **Excel fills the gaps** — any week the PDF doesn't have yet is taken from the Excel
  (and vice-versa: early weeks only in the PDF are taken from there).
- **A `$0` / blank week is never published.** Every row is validated (`_make_record`)
  and dropped unless it has a real, positive Handle *before* the two sources are merged.
  So an unpublished week in one format can't overwrite a real value in the other.

If you ever change the merge, keep those three rules — they're the whole reason the series
has no holes.

**Change detection** (`compare_data.py`) flags: new weekly data, a GGR swing >20% for an
existing operator, and operators added or removed. Any of those (or `FORCE_SEND`) triggers
an email.

---

## 7. What each run produces

| File | What it is |
|------|-----------|
| `ny_gaming_data.csv` | The master dataset. One row per operator per week. Columns: `Date, Handle, GGR, Brand`. |
| `ny_gaming_analysis.xlsx` | 5 sheets — Handle, GGR, Hold, Handle YoY %, GGR YoY % — by operator and Statewide. |
| `ny_gaming_weekly_exhibit.xlsx` | The polished 5-week exhibit for the featured brands (DraftKings, FanDuel, BetMGM, Fanatics) + Statewide, with Handle/GGR/Hold and year-over-year. |
| `data_archive/latest/` | Snapshot of the last run's CSV — the baseline the next run diffs against. |
| `data_changes.json` | Log of detected changes. |

Sample of `ny_gaming_data.csv`:

```csv
Date,Handle,GGR,Brand
2022-01-09,67420615,8582934.0,Caesars Sport Book
2022-01-09,38505013,7026956.0,DraftKings Sport Book
2022-01-09,63236093,-2725965.0,FanDuel      ← negative GGR: bettors won net that week (kept, not a bug)
```

Every notification email attaches all three spreadsheets (analysis workbook, exhibit,
and the raw CSV).

---

## 8. Common maintenance tasks & gotchas

- **An operator is added or drops out.** Update the operator list in **three** places so
  they stay in sync:
  1. `REPORTS` in `download_reports.py` (the download URLs),
  2. `brand_mapping` in `extract_to_csv_v2.py` (file name → display name),
  3. `FEATURED_BRANDS` in `create_weekly_exhibit.py` (only if you want them on the exhibit).
- **The state changes a report URL.** Symptom: that operator's download fails but others
  succeed. Fix the operator's `excel_url` / `pdf_url` in `download_reports.py`.
- **Emails stopped.** Check cron-job.org (section 3) first, then that the GitHub secrets
  haven't expired (Gmail App Passwords get revoked if 2FA is reset).
- **A week shows negative GGR.** That's legitimate (bettors won net that week). The
  pipeline intentionally keeps it — don't treat it as a bug.
- **Adding the public web form.** It's fully built in `web/` but not deployed. See
  [`docs/setup_public_form.md`](docs/setup_public_form.md). It lets someone enter an email
  and get a one-off report; it just calls the same `ny-gaming-manual.yml` workflow.

---

## 9. Provenance

- **Live source repo:** `github.com/nosherzapoo/OSBdata` (holds the full history and the
  running `data_archive/`). This folder is a clean, self-contained copy of the pipeline.
- **Original author:** Nosher Ali Khan.
- **Handed off:** 2026-07-02.
