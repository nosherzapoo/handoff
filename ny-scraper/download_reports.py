#!/usr/bin/env python3
"""
NY State Gaming Reports Downloader
Downloads all weekly reports from gaming.ny.gov efficiently using parallel processing.

For each operator we download BOTH the PDF and the Excel report:
  * The PDF is the most reliably up-to-date source (the Excel file is sometimes
    published late / without the latest week), so it is the primary source and
    its value wins for any week it contains.
  * The Excel file only fills weeks the PDF is missing.

When fetching a file we resolve the site's ``-excel`` / ``-pdf`` redirect to the
real document URL and then prefer the ``_2`` re-upload variant (the site appends
``_2`` when a report is re-published), falling back to the resolved pointer and
finally the un-suffixed base name.
"""

import asyncio
import re
import aiohttp
import aiofiles
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Expected content types per kind, used to reject HTML error pages served with 200.
CONTENT_TYPES = {
    'excel': 'spreadsheetml',
    'pdf': 'pdf',
}

# Report configurations. Each operator exposes an Excel and a PDF endpoint that
# only differ by the trailing ``-excel`` / ``-pdf`` slug.
REPORTS = [
    {
        "name": "Bally Bet",
        "excel_url": "https://gaming.ny.gov/ballybet-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/ballybet-weekly-report-pdf",
        "filename": "Bally_Bet_Weekly_Report",
    },
    {
        "name": "BetMGM",
        "excel_url": "https://gaming.ny.gov/betmgm-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/betmgm-weekly-report-pdf",
        "filename": "BetMGM_Weekly_Report",
    },
    {
        "name": "Caesars Sport Book",
        "excel_url": "https://gaming.ny.gov/caesars-sport-book-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/caesars-sport-book-weekly-report-pdf",
        "filename": "Caesars_Sport_Book_Weekly_Report",
    },
    {
        "name": "DraftKings Sport Book",
        "excel_url": "https://gaming.ny.gov/draftkings-sport-book-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/draftkings-sport-book-weekly-report-pdf",
        "filename": "DraftKings_Sport_Book_Weekly_Report",
    },
    {
        "name": "ESPN Bet (Wynn Interactive)",
        "excel_url": "https://gaming.ny.gov/wynn-interactive-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/wynn-interactive-weekly-report-pdf",
        "filename": "ESPN_Bet_Wynn_Interactive_Weekly_Report",
    },
    {
        "name": "Fanatics",
        "excel_url": "https://gaming.ny.gov/fanatics-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/fanatics-weekly-report-pdf",
        "filename": "Fanatics_Weekly_Report",
    },
    {
        "name": "FanDuel",
        "excel_url": "https://gaming.ny.gov/fanduel-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/fanduel-weekly-report-pdf",
        "filename": "FanDuel_Weekly_Report",
    },
    {
        "name": "Resorts World Bet",
        "excel_url": "https://gaming.ny.gov/resorts-world-bet-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/resorts-world-bet-weekly-report-pdf",
        "filename": "Resorts_World_Bet_Weekly_Report",
    },
    {
        "name": "Rush Street Interactive",
        "excel_url": "https://gaming.ny.gov/rush-street-interactive-weekly-report-excel",
        "pdf_url": "https://gaming.ny.gov/rush-street-interactive-weekly-report-pdf",
        "filename": "Rush_Street_Interactive_Weekly_Report",
    },
]


def candidate_urls(resolved_url: str):
    """Build the ordered list of document URLs to try for a resolved report URL.

    The site appends ``_2`` (``_1``, ``_3`` ...) to a file name when a report is
    re-uploaded. We prefer the ``_2`` re-upload, then the URL the site's redirect
    actually resolved to (guaranteed to exist), then the un-suffixed base name.
    Duplicates are removed while preserving order.
    """
    head, _, ext = resolved_url.rpartition('.')
    stem = re.sub(r'_\d+$', '', head)  # strip any trailing _<n>
    ordered = [f"{stem}_2.{ext}", resolved_url, f"{stem}.{ext}"]

    seen = set()
    candidates = []
    for url in ordered:
        if url not in seen:
            seen.add(url)
            candidates.append(url)
    return candidates


class NYGamingReportsDownloader:
    """Efficient downloader for NY State Gaming reports using async/await."""

    def __init__(self, output_dir: str = None):
        """Initialize the downloader with output directory."""
        if output_dir is None:
            today = datetime.now().strftime("%Y-%m-%d")
            output_dir = f"NY_State_Reports_{today}"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=300, connect=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _download_kind(self, name, endpoint_url, dest_path, kind):
        """Resolve ``endpoint_url`` then download the best matching document.

        Returns (success: bool, message: str).
        """
        expected = CONTENT_TYPES[kind]
        try:
            # Resolve the redirect to discover the real document URL (and grab the
            # body in the same request so we don't re-fetch the resolved file).
            async with self.session.get(endpoint_url) as response:
                if response.status != 200:
                    return False, f"HTTP {response.status}: {response.reason}"
                resolved_url = str(response.url)
                resolved_ctype = response.headers.get('Content-Type', '')
                resolved_body = await response.read()

            for url in candidate_urls(resolved_url):
                if url == resolved_url:
                    ctype, body = resolved_ctype, resolved_body
                else:
                    async with self.session.get(url) as r:
                        if r.status != 200:
                            continue
                        ctype = r.headers.get('Content-Type', '')
                        body = await r.read()

                if expected not in ctype.lower():
                    logger.warning(
                        f"  {name} [{kind}]: unexpected content-type '{ctype}' for {url}; skipping"
                    )
                    continue

                async with aiofiles.open(dest_path, 'wb') as f:
                    await f.write(body)

                chosen = '(resolved)' if url == resolved_url else url.rsplit('/', 1)[-1]
                logger.info(f"  ✅ {name} [{kind}]: {len(body):,} bytes from {chosen}")
                return True, f"{len(body):,} bytes"

            return False, "no valid document variant found"

        except asyncio.TimeoutError:
            return False, "Request timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"

    async def download_single_report(self, report):
        """Download both the PDF and Excel report for a single operator.

        Returns (report_name, success, message). Success requires at least one of
        the two formats so a single missing file does not fail the operator.
        """
        logger.info(f"Starting download: {report['name']}")

        pdf_ok, pdf_msg = await self._download_kind(
            report['name'], report['pdf_url'],
            self.output_dir / f"{report['filename']}.pdf", 'pdf',
        )
        excel_ok, excel_msg = await self._download_kind(
            report['name'], report['excel_url'],
            self.output_dir / f"{report['filename']}.xlsx", 'excel',
        )

        if pdf_ok or excel_ok:
            return report['name'], True, f"pdf: {pdf_msg} | excel: {excel_msg}"
        return report['name'], False, f"pdf: {pdf_msg} | excel: {excel_msg}"

    async def download_all_reports(self):
        """
        Download all reports concurrently.

        Returns:
            Dictionary mapping report names to success status
        """
        logger.info(f"🚀 Starting download of {len(REPORTS)} reports to {self.output_dir}")
        start_time = datetime.now()

        # Create all download tasks
        tasks = [self.download_single_report(report) for report in REPORTS]

        # Execute all downloads concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        success_count = 0
        failed_reports = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ Unexpected error: {result}")
                failed_reports.append(f"Unknown error: {result}")
            else:
                name, success, message = result
                if success:
                    success_count += 1
                else:
                    failed_reports.append(f"{name}: {message}")

        # Calculate timing
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Summary
        logger.info(f"\n📊 Download Summary:")
        logger.info(f"   ✅ Successful: {success_count}/{len(REPORTS)}")
        logger.info(f"   ❌ Failed: {len(failed_reports)}")
        logger.info(f"   ⏱️  Duration: {duration:.2f} seconds")
        logger.info(f"   📁 Output: {self.output_dir.absolute()}")

        if failed_reports:
            logger.error(f"\n❌ Failed downloads:")
            for failure in failed_reports:
                logger.error(f"   • {failure}")

        return success_count == len(REPORTS)

async def main():
    """Main function to run the downloader."""
    try:
        async with NYGamingReportsDownloader() as downloader:
            success = await downloader.download_all_reports()

            if success:
                logger.info("🎉 All downloads completed successfully!")
                return 0
            else:
                logger.error("💥 Some downloads failed!")
                return 1

    except KeyboardInterrupt:
        logger.info("\n🛑 Download interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    try:
        import aiohttp
        import aiofiles
    except ImportError as e:
        print("❌ Missing required packages. Please install them:")
        print("   pip install aiohttp aiofiles")
        print(f"   Error: {e}")
        sys.exit(1)

    sys.exit(asyncio.run(main()))
