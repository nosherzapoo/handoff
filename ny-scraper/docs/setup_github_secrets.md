# GitHub Secrets Setup for NY Gaming Data Monitor

## Required GitHub Secrets

To enable email notifications, you need to configure the following secrets in your GitHub repository:

### 1. Go to Repository Settings
- Navigate to your GitHub repository
- Click on "Settings" tab
- Click on "Secrets and variables" → "Actions"

### 2. Add the following secrets:

#### Email Configuration
- **`EMAIL_USER`**: Your email address (e.g., `your-email@gmail.com`)
- **`EMAIL_PASS`**: Your email app password (see instructions below)
- **`SMTP_SERVER`**: SMTP server (default: `smtp.gmail.com`)
- **`SMTP_PORT`**: SMTP port (default: `587`)

## Email Setup Instructions

### For Gmail (Most Common):
**You MUST use an App Password, NOT your regular Gmail password!**

#### Step-by-Step Gmail App Password Setup:
1. **Enable 2-Factor Authentication** (Required):
   - Go to https://myaccount.google.com/security
   - Enable "2-Step Verification" if not already enabled

2. **Generate App Password**:
   - Go to https://myaccount.google.com/apppasswords
   - Or: Google Account → Security → 2-Step Verification → App passwords
   - Select app: "Mail"
   - Select device: "Other (Custom name)" → Enter "GitHub Actions"
   - Click "Generate"
   - **Copy the 16-character password** (no spaces, formatted as: xxxx xxxx xxxx xxxx)

3. **Add to GitHub Secrets**:
   - Go to your repo: Settings → Secrets and variables → Actions
   - Add `EMAIL_USER`: Your full Gmail address (e.g., `yourname@gmail.com`)
   - Add `EMAIL_PASS`: The 16-character App Password (paste exactly as shown)
   - Add `SMTP_SERVER`: `smtp.gmail.com`
   - Add `SMTP_PORT`: `587`
   - Add `NOTIFICATION_EMAIL`: `nosher-ali.khan@bernsteinsg.com`

#### Troubleshooting Gmail Errors:
- **Error 535 "Username and Password not accepted"**:
  - ✅ Make sure you're using an App Password, not your regular password
  - ✅ Verify 2-Factor Authentication is enabled
  - ✅ Check that EMAIL_USER is your full email address
  - ✅ Ensure EMAIL_PASS has no extra spaces (should be 16 characters)
  
- **If App Passwords option doesn't appear**:
  - You must have 2-Factor Authentication enabled first

### For Other Email Providers:
- **Outlook/Hotmail**: `smtp-mail.outlook.com`, port `587`
- **Yahoo**: `smtp.mail.yahoo.com`, port `587`
- **Custom SMTP**: Use your organization's SMTP settings

## Testing the Setup

After configuring the secrets, you can test the workflow by:

1. Going to the "Actions" tab in your repository
2. Clicking on "NY Gaming Data Monitor"
3. Clicking "Run workflow" to trigger manually

## Notification Email

The system will send notifications to: `nosher-ali.khan@bernsteinsg.com`

## Schedule Summary

- **Thursday**: Every 2 hours (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
- **Friday 4AM-Noon**: Every 15 minutes
- **Friday 1PM-11PM**: Every hour

## Data Storage

- Current data: `ny_gaming_data.csv`
- Archived data: `data_archive/YYYYMMDD_HHMMSS/`
- Change log: `data_changes.json`
