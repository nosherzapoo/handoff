#!/usr/bin/env python3
"""
NY State Gaming Reports Data Extractor V2
Extracts weekly Handle/GGR data from the downloaded reports into a single CSV.

Each operator is published as both an Excel file and a PDF. They carry the same
weekly figures, but the PDF is the more reliably up-to-date source (the Excel is
sometimes published late / without the latest week).

So for every operator we extract both and merge per week-ending date: the PDF
value wins whenever it exists and the Excel only fills weeks the PDF is missing.
"""

import re
import pandas as pd
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# A PDF data row looks like:  03/29/26 $3,233,405 $317,181
# A negative value is parenthesised with the $ inside the parens, e.g.
# 06/14/26 $44,703,354 ($2,481,951). Each money token may therefore be wrapped
# in ( ) and prefixed with $; _parse_money() interprets the parentheses as a
# negative sign.
PDF_ROW_RE = re.compile(
    r'^(\d{2}/\d{2}/\d{2})\s+(\(?\$?[\d,]+\)?)\s+(\(?\$?[\d,]+\)?)\s*$'
)


def _parse_money(token: str):
    """Parse a money token like '3,233,405' or '(123)' into a float, or None."""
    token = token.strip().replace(',', '').replace('$', '')
    negative = token.startswith('(') and token.endswith(')')
    token = token.strip('()')
    if not token:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


class NYGamingDataExtractorV2:
    """Extractor for NY State Gaming reports (Excel + PDF) -> CSV."""

    def __init__(self, reports_dir=None):
        """Initialize the extractor.

        If reports_dir is not provided, automatically pick the most recent
        directory matching the pattern NY_State_Reports_*/ in the current
        working directory.
        """
        if reports_dir is None:
            root = Path('.')
            candidates = sorted(
                [p for p in root.glob('NY_State_Reports_*') if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                logger.warning("No NY_State_Reports_* directory found; defaulting to current directory")
                self.reports_dir = Path('.')
            else:
                self.reports_dir = candidates[0]
                logger.info(f"Using reports directory: {self.reports_dir}")
        else:
            self.reports_dir = Path(reports_dir)
        self.all_data = []

        # Brand mapping from report file stem to display name.
        self.brand_mapping = {
            'Bally_Bet_Weekly_Report': 'Bally Bet',
            'BetMGM_Weekly_Report': 'BetMGM',
            'Caesars_Sport_Book_Weekly_Report': 'Caesars Sport Book',
            'DraftKings_Sport_Book_Weekly_Report': 'DraftKings Sport Book',
            'ESPN_Bet_Wynn_Interactive_Weekly_Report': 'ESPN Bet',
            'Fanatics_Weekly_Report': 'Fanatics',
            'FanDuel_Weekly_Report': 'FanDuel',
            'Resorts_World_Bet_Weekly_Report': 'Resorts World Bet',
            'Rush_Street_Interactive_Weekly_Report': 'Rush Street Interactive',
        }

    def _make_record(self, date_val, handle_val, ggr_val, brand):
        """Build a normalized record dict, or None if the row is not usable.

        A real reporting week is identified by a *positive handle* (wagers were
        placed). GGR is kept with whatever sign it has -- weekly GGR is regularly
        negative when bettors win net (e.g. 2026-06-14), and those weeks must not
        be dropped. Blank/future weeks (no handle/GGR) and pre-launch $0 weeks are
        excluded by the positive-handle requirement.
        """
        if pd.isna(date_val):
            return None

        # GGR must be a reported number, but may be zero or negative.
        try:
            ggr_val = float(ggr_val)
        except (TypeError, ValueError):
            return None
        if pd.isna(ggr_val):
            return None

        # Handle must be a positive number for the week to count as reported.
        try:
            handle_num = float(handle_val)
        except (TypeError, ValueError):
            return None
        if pd.isna(handle_num) or handle_num <= 0:
            return None

        try:
            date_norm = pd.to_datetime(date_val).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return None

        return {
            'Date': date_norm,
            'Handle': str(int(handle_num)),
            'GGR': ggr_val,
            'Brand': brand,
        }

    def extract_excel_records(self, file_path, brand):
        """Extract {date_str: record} from a single Excel file (gap-fill source)."""
        records = {}
        try:
            excel_file = pd.ExcelFile(file_path)
        except Exception as e:
            logger.error(f"  Error opening Excel {file_path.name}: {e}")
            return records

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

            # Find the header row (contains "Week-Ending")
            header_row = None
            for idx, row in df.iterrows():
                if pd.notna(row.iloc[0]) and 'Week-Ending' in str(row.iloc[0]):
                    header_row = idx
                    break
            if header_row is None:
                continue

            data_df = df.iloc[header_row + 1:].copy().dropna(how='all')

            # Known columns: 0=Date, 2=Handle, 5=GGR
            for _, row in data_df.iterrows():
                date_val = row.iloc[0] if len(row) > 0 else None
                handle_val = row.iloc[2] if len(row) > 2 else None
                ggr_val = row.iloc[5] if len(row) > 5 else None
                if pd.isna(date_val):
                    continue
                rec = self._make_record(date_val, handle_val, ggr_val, brand)
                if rec:
                    records[rec['Date']] = rec

        logger.info(f"    Excel: {len(records)} weeks")
        return records

    def extract_pdf_records(self, file_path, brand):
        """Extract {date_str: record} from a single PDF file (primary source)."""
        records = {}
        try:
            import pdfplumber
        except ImportError:
            logger.warning("    pdfplumber not installed; skipping PDF extraction")
            return records

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    for line in text.split('\n'):
                        match = PDF_ROW_RE.match(line.strip())
                        if not match:
                            continue
                        date_str, handle_str, ggr_str = match.groups()
                        try:
                            date_val = pd.to_datetime(date_str, format='%m/%d/%y')
                        except ValueError:
                            continue
                        rec = self._make_record(
                            date_val, _parse_money(handle_str), _parse_money(ggr_str), brand
                        )
                        if rec:
                            records[rec['Date']] = rec
        except Exception as e:
            logger.error(f"  Error reading PDF {file_path.name}: {e}")

        logger.info(f"    PDF:   {len(records)} weeks")
        return records

    def extract_operator(self, stem, brand):
        """Extract and merge one operator's Excel + PDF reports.

        PDF is preferred and wins for any week it reports. But the state does not
        publish both formats in lockstep -- sometimes a week lands on the PDF
        first, sometimes on the Excel first -- so we take the *union* of weeks and
        fall back to the Excel for any week the PDF does not have.

        Crucially, neither source can contribute a blank or $0 week: extraction
        runs every row through _make_record(), which drops any row without a
        positive handle. So an unpublished / zeroed-out PDF week simply never
        enters ``pdf_records`` and therefore never suppresses a real Excel week
        for the same date (and vice-versa). A 0 is never published.
        """
        logger.info(f"Processing {brand}...")
        excel_path = self.reports_dir / f"{stem}.xlsx"
        pdf_path = self.reports_dir / f"{stem}.pdf"

        excel_records = self.extract_excel_records(excel_path, brand) if excel_path.exists() else {}
        pdf_records = self.extract_pdf_records(pdf_path, brand) if pdf_path.exists() else {}

        # {**excel, **pdf}: union of both, PDF value winning on any shared week.
        merged = {**excel_records, **pdf_records}

        filled_from_excel = sorted(d for d in excel_records if d not in pdf_records)
        if filled_from_excel:
            logger.info(
                f"    Filled {len(filled_from_excel)} week(s) from Excel (PDF missing): "
                f"{', '.join(filled_from_excel)}"
            )
        only_in_pdf = sorted(d for d in pdf_records if d not in excel_records)
        if only_in_pdf:
            logger.info(
                f"    {len(only_in_pdf)} week(s) came only from the PDF (Excel missing): "
                f"{', '.join(only_in_pdf)}"
            )
        logger.info(
            f"    Merged: {len(merged)} weeks "
            f"(PDF {len(pdf_records)}, Excel {len(excel_records)}, Excel-only fills {len(filled_from_excel)})"
        )
        return list(merged.values())

    def extract_all_data(self):
        """Extract data from all operator reports (Excel + PDF) in the reports dir."""
        logger.info("🚀 Starting data extraction...")

        # Collect report stems present as either .xlsx or .pdf (ignore Excel temp files).
        stems = set()
        for path in list(self.reports_dir.glob('*.xlsx')) + list(self.reports_dir.glob('*.pdf')):
            if path.name.startswith('~$'):
                continue
            stems.add(path.stem)

        logger.info(f"Found {len(stems)} operator report set(s)")

        for stem in sorted(stems):
            brand = self.brand_mapping.get(stem, stem.replace('_', ' '))
            self.all_data.extend(self.extract_operator(stem, brand))
            logger.info(f"  Total records so far: {len(self.all_data)}")

        logger.info(f"✅ Extraction complete! Total records: {len(self.all_data)}")
        return self.all_data

    def save_to_csv(self, output_file="ny_gaming_data.csv"):
        """Save all extracted data to CSV."""
        if not self.all_data:
            logger.warning("No data to save!")
            return None

        df = pd.DataFrame(self.all_data)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(['Date', 'Brand'])

        output_path = Path(output_file)
        df.to_csv(output_path, index=False)

        logger.info(f"💾 Data saved: {len(df)} records, {df['Brand'].nunique()} brands")
        return output_path

def main():
    """Main function to run the extraction."""
    try:
        extractor = NYGamingDataExtractorV2()

        # Extract all data
        extractor.extract_all_data()

        # Save to CSV
        output_file = extractor.save_to_csv()

        if output_file:
            print(f"\n🎉 Data extraction complete!")
            print(f"📁 Output file: {output_file.absolute()}")
        else:
            print("❌ No data extracted!")
            return 1

    except Exception as e:
        logger.error(f"💥 Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
