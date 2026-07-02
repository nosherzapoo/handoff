#!/usr/bin/env node
/*
 * Pollstar Data Cloud -> concerts.csv
 *
 * Pulls every boxoffice report with EventDate >= 2010-01-01 from the (encrypted)
 * boxoffice2 API and writes a flat CSV.
 *
 * AUTH: put your bearer token in jwt.txt next to this file. Get it from the
 * logged-in site: DevTools -> Network -> Fetch/XHR -> a `boxoffice2?...` request
 * -> Copy as cURL -> take the value of the `Authorization:` header.
 * The SAME token is also the AES key source (cookie PS_U_TOKEN == this JWT), so
 * jwt.txt is the only secret needed. Token lasts ~30 days; refresh when expired.
 *
 * Encryption (reverse-engineered from chunk 523 / module 56382):
 *   resp        = JSON.parse(body)                 // outer body is a JSON string
 *   r           = Number(resp.slice(0,4))          // key offset
 *   ciphertext  = resp.slice(4)                    // base64
 *   key(32 chr) = JWT.substring(r, r+32)
 *   plaintext   = AES-256-CBC(decode(ciphertext), key=key, iv=key.slice(0,16)), PKCS7
 *
 * Resumable: each page is cached under pages/. Re-run to resume; delete pages/ to refetch.
 *
 *   node fetch_pollstar.js          # fetch all pages, then build concerts.csv
 *   node fetch_pollstar.js --csv    # rebuild concerts.csv from cached pages only
 */
const https = require("https");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const JWT = fs.readFileSync(path.join(HERE, "jwt.txt"), "utf8").trim();
const PAGES_DIR = path.join(HERE, "pages");
const CSV_PATH = path.join(HERE, "concerts.csv");

const PAGE_SIZE = 50000;     // server happily returns 50k/page (~25s each)
const CONCURRENCY = 3;       // polite; ~15 pages total
const RETRIES = 4;
const FILTER = encodeURIComponent("EventDate>=2010-01-01");

const COLUMNS = [
  "eventId", "eventDate", "endDate", "numShows", "headLiner", "support",
  "ticketsSold", "avgTicketsSold", "grossUSD", "avgGrossUSD", "venueName",
  "companyType", "city", "state", "stateAbbrev", "country", "capacity",
  "avgCapacitySold", "ticketPriceMin", "ticketPriceMax", "ticketPriceAvg",
  "currency", "promoter", "genre", "market", "hidden",
];

function urlFor(page, pageSize) {
  return `https://data.pollstar.com/data/v1/research/datacloud/boxoffice2` +
    `?filter=${FILTER}&page=${page}&pageSize=${pageSize}` +
    `&boxOfficeOnly=true&festivals=0&sortColumn=eventDate&sortAscending=false`;
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        Authorization: JWT,
        Accept: "application/json, text/plain, */*",
        Referer: "https://pollstar.com/",
        "User-Agent": "Mozilla/5.0",
      },
    }, (res) => {
      let d = "";
      res.on("data", (c) => (d += c));
      res.on("end", () => resolve({ status: res.statusCode, body: d }));
    }).on("error", reject);
  });
}

function decrypt(body) {
  const outer = JSON.parse(body);                 // body is a JSON-encoded string
  if (typeof outer !== "string") return outer;     // (defensive: already-plain payloads)
  const r = Number(outer.slice(0, 4));
  const ciphertext = outer.slice(4);
  const a = JWT.substring(r, r + 32);
  const key = Buffer.from(a, "utf8");
  const iv = Buffer.from(a.slice(0, 16), "utf8");
  const dec = crypto.createDecipheriv("aes-256-cbc", key, iv);
  const out = Buffer.concat([dec.update(Buffer.from(ciphertext, "base64")), dec.final()]);
  return JSON.parse(out.toString("utf8"));
}

async function fetchPage(page, pageSize) {
  let lastErr;
  for (let attempt = 0; attempt < RETRIES; attempt++) {
    try {
      const { status, body } = await httpGet(urlFor(page, pageSize));
      if (status === 401 || status === 403) {
        throw Object.assign(new Error(`auth failed (HTTP ${status}) — refresh jwt.txt`), { fatal: true });
      }
      if (status !== 200) throw new Error(`HTTP ${status}: ${body.slice(0, 120)}`);
      return decrypt(body);
    } catch (e) {
      if (e.fatal) throw e;
      lastErr = e;
      await new Promise((r) => setTimeout(r, 1500 * 2 ** attempt));
    }
  }
  throw new Error(`page ${page} failed after ${RETRIES} tries: ${lastErr.message}`);
}

function csvCell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

async function run() {
  fs.mkdirSync(PAGES_DIR, { recursive: true });

  // page 0: total count + first batch
  console.log("Fetching page 0 (probe + first batch) ...");
  const first = await fetchPage(0, PAGE_SIZE);
  const total = first.totalRows;
  const nPages = Math.ceil(total / PAGE_SIZE);
  console.log(`  totalRows=${total} -> ${nPages} pages of ${PAGE_SIZE}`);
  fs.writeFileSync(path.join(PAGES_DIR, "page-0.json"), JSON.stringify(first.events));

  // remaining pages, with a small concurrency pool
  const todo = [];
  for (let p = 1; p < nPages; p++) {
    if (!fs.existsSync(path.join(PAGES_DIR, `page-${p}.json`))) todo.push(p);
  }
  console.log(`Fetching ${todo.length} remaining pages (concurrency ${CONCURRENCY}) ...`);
  let done = 0;
  async function worker() {
    while (todo.length) {
      const p = todo.shift();
      const data = await fetchPage(p, PAGE_SIZE);
      fs.writeFileSync(path.join(PAGES_DIR, `page-${p}.json`), JSON.stringify(data.events));
      console.log(`  page ${p}: ${data.events.length} events  [${++done}/${todo.length + done}]`);
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  buildCsv(nPages);
}

function buildCsv(nPages) {
  console.log("Building concerts.csv ...");
  const out = fs.createWriteStream(CSV_PATH);
  out.write(COLUMNS.join(",") + "\n");
  const seen = new Set();
  let rows = 0, dupes = 0;
  const files = fs.readdirSync(PAGES_DIR).filter((f) => /^page-\d+\.json$/.test(f))
    .sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)));
  for (const f of files) {
    const events = JSON.parse(fs.readFileSync(path.join(PAGES_DIR, f), "utf8"));
    for (const ev of events) {
      if (seen.has(ev.eventId)) { dupes++; continue; }
      seen.add(ev.eventId);
      out.write(COLUMNS.map((c) => csvCell(ev[c])).join(",") + "\n");
      rows++;
    }
  }
  out.end();
  console.log(`Done: ${rows} unique rows (${dupes} dupes skipped) -> ${CSV_PATH}`);
}

if (process.argv.includes("--csv")) {
  buildCsv();
} else {
  run().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
}
