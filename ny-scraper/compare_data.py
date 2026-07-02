#!/usr/bin/env python3
"""
NY Gaming Data Comparison and Notification System
Compares new data with previous data and sends email notifications for changes.
"""

import pandas as pd
import os
import smtplib
import json
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NYGamingDataMonitor:
    """Monitors NY gaming data for changes and sends notifications."""
    
    def __init__(self):
        """Initialize the monitor."""
        self.current_data_file = "ny_gaming_data.csv"
        self.previous_data_file = "data_archive/latest/ny_gaming_data.csv"
        self.changes_log = "data_changes.json"
        
        # Email configuration from environment variables
        self.email_user = os.getenv('EMAIL_USER')
        self.email_pass = os.getenv('EMAIL_PASS')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        
    def load_current_data(self):
        """Load the current data."""
        if not Path(self.current_data_file).exists():
            logger.error(f"Current data file {self.current_data_file} not found!")
            return None
            
        df = pd.read_csv(self.current_data_file)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    
    def load_previous_data(self):
        """Load the previous data."""
        if not Path(self.previous_data_file).exists():
            logger.info("No previous data found - this is the first run")
            return None
            
        df = pd.read_csv(self.previous_data_file)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    
    def compare_data(self, current_df, previous_df):
        """Compare current and previous data to detect changes."""
        if previous_df is None:
            logger.info("No previous data to compare - treating as new data")
            return {
                'is_new_data': True,
                'total_records': len(current_df),
                'date_range': f"{current_df['Date'].min()} to {current_df['Date'].max()}",
                'brands': current_df['Brand'].nunique(),
                'changes': []
            }
        
        changes = []
        
        # Compare total records
        current_count = len(current_df)
        previous_count = len(previous_df)
        if current_count != previous_count:
            changes.append({
                'type': 'record_count',
                'description': f'Total records changed from {previous_count} to {current_count}',
                'previous': previous_count,
                'current': current_count
            })
        
        # Compare date ranges
        current_date_range = (current_df['Date'].min(), current_df['Date'].max())
        previous_date_range = (previous_df['Date'].min(), previous_df['Date'].max())
        
        if current_date_range != previous_date_range:
            changes.append({
                'type': 'date_range',
                'description': f'Date range changed from {previous_date_range[0]} to {previous_date_range[1]} to {current_date_range[0]} to {current_date_range[1]}',
                'previous': str(previous_date_range),
                'current': str(current_date_range)
            })
        
        # Compare latest data by brand
        current_latest = current_df.groupby('Brand').agg({
            'Date': 'max',
            'GGR': 'last',
            'Handle': 'last'
        }).reset_index()
        
        previous_latest = previous_df.groupby('Brand').agg({
            'Date': 'max',
            'GGR': 'last',
            'Handle': 'last'
        }).reset_index()
        
        # Check for new brands
        current_brands = set(current_latest['Brand'])
        previous_brands = set(previous_latest['Brand'])
        
        new_brands = current_brands - previous_brands
        removed_brands = previous_brands - current_brands
        
        if new_brands:
            changes.append({
                'type': 'new_brands',
                'description': f'New brands detected: {", ".join(new_brands)}',
                'brands': list(new_brands)
            })
        
        if removed_brands:
            changes.append({
                'type': 'removed_brands',
                'description': f'Brands removed: {", ".join(removed_brands)}',
                'brands': list(removed_brands)
            })
        
        # Check for significant GGR changes in existing brands
        for brand in current_brands & previous_brands:
            current_brand_data = current_latest[current_latest['Brand'] == brand].iloc[0]
            previous_brand_data = previous_latest[previous_latest['Brand'] == brand].iloc[0]
            
            # Check if latest date changed
            if current_brand_data['Date'] != previous_brand_data['Date']:
                changes.append({
                    'type': 'new_weekly_data',
                    'description': f'{brand}: New weekly data available',
                    'brand': brand,
                    'new_date': str(current_brand_data['Date']),
                    'previous_date': str(previous_brand_data['Date'])
                })
            
            # Check for significant GGR changes (more than 20% change)
            current_ggr = current_brand_data['GGR']
            previous_ggr = previous_brand_data['GGR']
            
            if previous_ggr > 0:
                ggr_change_pct = ((current_ggr - previous_ggr) / previous_ggr) * 100
                if abs(ggr_change_pct) > 20:  # 20% threshold
                    changes.append({
                        'type': 'significant_ggr_change',
                        'description': f'{brand}: GGR changed by {ggr_change_pct:.1f}% (${previous_ggr:,.0f} → ${current_ggr:,.0f})',
                        'brand': brand,
                        'change_percent': ggr_change_pct,
                        'previous_ggr': previous_ggr,
                        'current_ggr': current_ggr
                    })
        
        return {
            'is_new_data': False,
            'total_records': current_count,
            'date_range': f"{current_df['Date'].min()} to {current_df['Date'].max()}",
            'brands': current_df['Brand'].nunique(),
            'changes': changes
        }
    
    def send_notification(self, comparison_result, excel_file=None, additional_files=None):
        """Send email notification about data changes."""
        if not self.email_user or not self.email_pass or not self.notification_email:
            logger.warning("Email credentials not configured - skipping notification")
            return
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.notification_email
            msg['Subject'] = f"NY Gaming Data Update - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Create email body
            body = self.create_email_body(comparison_result)
            msg.attach(MIMEText(body, 'html'))

            def attach_file(filepath, mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
                if Path(filepath).exists():
                    with open(filepath, "rb") as f:
                        part = MIMEBase(*mime_type.split('/'))
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={Path(filepath).name}')
                        msg.attach(part)
                    logger.info(f"📎 Attached: {filepath}")

            # Attach Excel analysis file if provided
            if excel_file:
                attach_file(excel_file)

            # Attach any additional files (e.g. weekly exhibit)
            if additional_files:
                for f in additional_files:
                    attach_file(f)
            
            # Also attach current data CSV
            if Path(self.current_data_file).exists():
                with open(self.current_data_file, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {self.current_data_file}'
                    )
                    msg.attach(part)
            
            # Parse multiple recipients (comma-separated)
            recipients = [email.strip() for email in self.notification_email.split(',')]
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_pass)
            text = msg.as_string()
            server.sendmail(self.email_user, recipients, text)
            server.quit()
            
            logger.info(f"📧 Notification sent to {', '.join(recipients)}")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def create_email_body(self, comparison_result):
        """Create HTML email body."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""<html><body>
        <h2>NY Gaming Data Update Report</h2>
        <p><strong>Timestamp:</strong> {timestamp}</p>
        <h3>Data Summary</h3>
        <ul>
        <li><strong>Total Records:</strong> {comparison_result['total_records']:,}</li>
        <li><strong>Date Range:</strong> {comparison_result['date_range']}</li>
        <li><strong>Brands:</strong> {comparison_result['brands']}</li>
        </ul>"""
        
        if comparison_result['is_new_data']:
            html += "<h3>🆕 New Data Detected</h3><p>First data collection or major update.</p>"
        elif comparison_result['changes']:
            html += "<h3>📊 Changes Detected</h3><ul>"
            for change in comparison_result['changes']:
                html += f"<li><strong>{change['type'].replace('_', ' ').title()}:</strong> {change['description']}</li>"
            html += "</ul>"
        else:
            html += "<h3>✅ No Changes</h3><p>No significant changes detected.</p>"
        
        html += "<hr><p><em>Automated report from NY Gaming Data Monitor.</em></p></body></html>"
        return html
    
    def create_excel_report(self, current_df):
        """Create comprehensive Excel report with multiple workbooks."""
        logger.info("📊 Creating Excel report...")
        
        # Sort data by date (most recent first)
        df = current_df.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date', ascending=False)
        
        # Get unique brands and dates
        brands = sorted(df['Brand'].unique())
        dates = sorted(df['Date'].unique(), reverse=True)  # Most recent first
        
        # Create pivot tables for each metric
        with pd.ExcelWriter('ny_gaming_analysis.xlsx', engine='openpyxl') as writer:
            
            # 1. Handle Workbook
            handle_pivot = df.pivot_table(
                index='Date', 
                columns='Brand', 
                values='Handle', 
                aggfunc='sum',
                fill_value=0
            )
            handle_pivot = handle_pivot.reindex(dates)
            handle_pivot['Statewide'] = handle_pivot.sum(axis=1)
            handle_pivot.to_excel(writer, sheet_name='Handle')
            
            # 2. GGR Workbook
            ggr_pivot = df.pivot_table(
                index='Date', 
                columns='Brand', 
                values='GGR', 
                aggfunc='sum',
                fill_value=0
            )
            ggr_pivot = ggr_pivot.reindex(dates)
            ggr_pivot['Statewide'] = ggr_pivot.sum(axis=1)
            ggr_pivot.to_excel(writer, sheet_name='GGR')
            
            # 3. Hold Workbook (GGR/Handle) - as percentage
            hold_pivot = ggr_pivot.div(handle_pivot.replace(0, np.nan))
            hold_pivot = hold_pivot.replace([np.inf, -np.inf, np.nan], '')  # Keep blank for errors
            hold_pivot.to_excel(writer, sheet_name='Hold')
            
            # 4. Handle YoY Workbook - as percentage
            handle_yoy = self.calculate_yoy(handle_pivot)
            handle_yoy = handle_yoy.replace([np.inf, -np.inf, np.nan], '')  # Keep blank for errors
            handle_yoy.to_excel(writer, sheet_name='Handle (YoY)')
            
            # 5. GGR YoY Workbook - as percentage
            ggr_yoy = self.calculate_yoy(ggr_pivot)
            ggr_yoy = ggr_yoy.replace([np.inf, -np.inf, np.nan], '')  # Keep blank for errors
            ggr_yoy.to_excel(writer, sheet_name='GGR (YoY)')
            
            # Apply percentage formatting to Hold and YoY sheets
            workbook = writer.book
            
            # Format Hold sheet as percentage
            hold_sheet = writer.sheets['Hold']
            for row in range(2, hold_sheet.max_row + 1):  # Skip header row
                for col in range(2, hold_sheet.max_column + 1):  # Skip date column
                    cell = hold_sheet.cell(row=row, column=col)
                    if cell.value != '' and cell.value is not None:
                        cell.number_format = '0.00%'
            
            # Format Handle YoY sheet as percentage
            handle_yoy_sheet = writer.sheets['Handle (YoY)']
            for row in range(2, handle_yoy_sheet.max_row + 1):
                for col in range(2, handle_yoy_sheet.max_column + 1):
                    cell = handle_yoy_sheet.cell(row=row, column=col)
                    if cell.value != '' and cell.value is not None:
                        cell.number_format = '0.00%'
            
            # Format GGR YoY sheet as percentage
            ggr_yoy_sheet = writer.sheets['GGR (YoY)']
            for row in range(2, ggr_yoy_sheet.max_row + 1):
                for col in range(2, ggr_yoy_sheet.max_column + 1):
                    cell = ggr_yoy_sheet.cell(row=row, column=col)
                    if cell.value != '' and cell.value is not None:
                        cell.number_format = '0.00%'
        
        logger.info("✅ Excel report created: ny_gaming_analysis.xlsx")
        return 'ny_gaming_analysis.xlsx'
    
    def calculate_yoy(self, df):
        """Calculate Year-over-Year percentage change using 364 days (52 weeks)."""
        yoy_df = df.copy()

        def calc_for_series(series):
            values = []
            for date in df.index:
                current_value = series.loc[date]
                last_year_date = date - pd.DateOffset(days=364)
                window = df.index[(df.index >= last_year_date - pd.DateOffset(days=7)) &
                                  (df.index <= last_year_date + pd.DateOffset(days=7))]
                if len(window) == 0:
                    values.append('')
                    continue
                closest_date = min(window, key=lambda x: abs((x - last_year_date).days))
                last_year_value = series.loc[closest_date]
                if last_year_value == 0 or pd.isna(last_year_value):
                    values.append('')
                else:
                    values.append((current_value / last_year_value) - 1)
            return values

        for col in df.columns:
            yoy_df[col] = calc_for_series(df[col])

        return yoy_df
    
    def save_changes_log(self, comparison_result):
        """Save changes to log file."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'comparison': comparison_result
        }
        
        # Load existing log
        if Path(self.changes_log).exists():
            with open(self.changes_log, 'r') as f:
                log_data = json.load(f)
        else:
            log_data = []
        
        # Add new entry
        log_data.append(log_entry)
        
        # Keep only last 100 entries
        if len(log_data) > 100:
            log_data = log_data[-100:]
        
        # Save log
        with open(self.changes_log, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    def run_monitoring(self):
        """Run the complete monitoring process."""
        logger.info("🔍 Starting NY Gaming Data Monitoring...")
        
        # Load data
        current_data = self.load_current_data()
        if current_data is None:
            logger.error("Failed to load current data")
            return False
        
        previous_data = self.load_previous_data()
        
        # Compare data
        comparison_result = self.compare_data(current_data, previous_data)
        
        # Log results
        logger.info(f"📊 Data Summary: {comparison_result['total_records']} records, {comparison_result['brands']} brands")
        
        if comparison_result['changes']:
            logger.info(f"📈 Changes detected: {len(comparison_result['changes'])}")
            for change in comparison_result['changes']:
                logger.info(f"  • {change['description']}")
        else:
            logger.info("✅ No changes detected")
        
        # Save changes log
        self.save_changes_log(comparison_result)
        
        # Create Excel report and send notification if there are changes (or FORCE_SEND is set)
        force_send = os.getenv('FORCE_SEND', '').lower() == 'true'
        if force_send or comparison_result['changes'] or comparison_result['is_new_data']:
            # Create comprehensive Excel report
            excel_file = self.create_excel_report(current_data)

            # Attach the weekly exhibit whenever it was generated. Both the
            # scheduled and manual workflows build it before this step, so any
            # email that goes out includes the exhibit alongside the numbers.
            additional = []
            exhibit_file = 'ny_gaming_weekly_exhibit.xlsx'
            if Path(exhibit_file).exists():
                additional.append(exhibit_file)
                logger.info(f"📋 Including weekly exhibit in email: {exhibit_file}")

            # Send notification with Excel attachment(s)
            self.send_notification(comparison_result, excel_file, additional_files=additional or None)
            
            # Save current data as the new baseline for next comparison
            import shutil
            Path(self.previous_data_file).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.current_data_file, self.previous_data_file)
            logger.info("📁 Updated baseline data for next comparison")
        else:
            # Still update the baseline even if no changes
            import shutil
            Path(self.previous_data_file).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.current_data_file, self.previous_data_file)
            logger.info("📁 Updated baseline data (no changes detected)")
        
        logger.info("✅ Monitoring complete")
        return True

def main():
    """Main function."""
    monitor = NYGamingDataMonitor()
    success = monitor.run_monitoring()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
