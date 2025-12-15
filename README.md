# Splitwise Expense Dashboard

Track your Splitwise expenses with an interactive dashboard, automatic cloud backups, and monthly email reports.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

This application connects to your Splitwise account, fetches your expense history, and generates:

- **Interactive HTML Dashboard** — Charts, filters, and monthly summaries
- **Complete Data Backup** — JSON and CSV files with all your Splitwise data
- **Email Reports** — Monthly summaries sent directly to your inbox

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- A [Splitwise](https://www.splitwise.com) account with expenses

### Installation

**1. Clone this repository**

```bash
git clone https://github.com/mduse88/family_expenses.git
cd family_expenses
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r Requirements.txt
```

**3. Get your Splitwise API key**

1. Visit [Splitwise Apps](https://secure.splitwise.com/apps) and register a new application
2. Copy the **API Key** (see [Splitwise API Key](#splitwise-api-key-required) for detailed steps)

**4. Configure your credentials**

```bash
cp .env.example .env
```

Open `.env` in a text editor and add your API key:

```env
# Required
api_key=YOUR_SPLITWISE_API_KEY

# Optional: limit to a specific Splitwise group
group_id=YOUR_GROUP_ID

# Optional: customize the dashboard title
DASHBOARD_TITLE=My Family Expenses
```

**5. Generate your dashboard**

```bash
python family_expenses.py --local
```

This creates three files in the `output/` folder:

| File | Description |
|------|-------------|
| `YYYY-MM-DD_expenses.json` | Complete backup of all Splitwise data |
| `YYYY-MM-DD_expenses.csv` | Same data in spreadsheet format |
| `YYYY-MM-DD_expenses_dashboard.html` | Interactive dashboard |

**6. Open the dashboard**

```bash
open output/*_expenses_dashboard.html
```

You should see your expenses displayed with charts, filters, and a monthly summary.

### Optional: Cloud Backup & Email Reports

To enable automatic Google Drive backups and email reports:

1. Set up [Google Drive OAuth](#google-drive-oauth-for-cloud-backup) credentials
2. Set up a [Gmail App Password](#gmail-app-password-for-email-automation)
3. Run with additional flags:

```bash
# Upload to Google Drive
python family_expenses.py

# Upload and send email report
python family_expenses.py --email
```

### Optional: Automated Monthly Reports

Set up GitHub Actions to run automatically on the 1st of each month. See [GitHub Actions Automation](#github-actions-automation) for setup instructions.

---

## Features

| Feature | Description |
|---------|-------------|
| **Interactive Dashboard** | Monthly spending charts, category breakdown, filters, and search |
| **Complete Data Backup** | JSON and CSV exports with all Splitwise fields (payments, users, repayments) |
| **Full History Retrieval** | Fetches all expenses from your first to your most recent via automatic pagination |
| **Email Reports** | Monthly summary with spending trends, top categories, and a link to the dashboard |
| **Google Drive Integration** | Automatic cloud backup with optional sharing to family members |
| **CSV Export** | Download filtered data directly from the dashboard |

---

## Project Structure

```
├── family_expenses.py          # Main CLI application
├── src/
│   ├── config.py               # Environment configuration
│   ├── splitwise_client.py     # Splitwise API integration
│   ├── dashboard.py            # HTML dashboard generator
│   ├── email_sender.py         # Email report sender
│   ├── gdrive.py               # Google Drive integration
│   └── stats.py                # Statistics calculations
├── templates/
│   └── dashboard.html          # Dashboard template (Jinja2)
├── .github/workflows/
│   └── expense_report.yml      # GitHub Actions workflow
└── Requirements.txt            # Python dependencies
```

---

## Configuration Details

This section provides detailed setup instructions for each integration.

### Splitwise API Key (Required)

<details>
<summary>How to get your Splitwise API Key</summary>

1. Go to [Splitwise Apps](https://secure.splitwise.com/apps)
2. Click **Register your application**
3. Fill in the form:
   - Application name: `Expense Dashboard`
   - Description: `Personal expense tracking`
   - Homepage URL: `https://github.com`
4. Click **Register and get API key**
5. Copy the **API Key** (not the Consumer Key/Secret)

**Finding your Group ID** (optional):

Open Splitwise in your browser, navigate to your group, and copy the number from the URL:
`https://www.splitwise.com/groups/XXXXXXX` → `XXXXXXX` is your Group ID

</details>

### Gmail App Password (Optional)

<details>
<summary>How to create a Gmail App Password</summary>

> **Requirement:** 2-Step Verification must be enabled on your Google Account.

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Under "Signing in to Google", click **2-Step Verification**
3. Scroll down and click **App passwords**
4. Select app: **Mail**
5. Select device: **Other (Custom name)** → Enter `Expense Dashboard`
6. Click **Generate**
7. Copy the 16-character password

> **Note:** Store this password securely — you cannot view it again.

</details>

### Google Drive OAuth (Optional)

<details>
<summary>How to set up Google Drive OAuth</summary>

**Step 1: Create a Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Library**
4. Search for **Google Drive API** and enable it

**Step 2: Configure OAuth Consent Screen**

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type
3. Fill in required fields (App name, support email, developer contact)
4. On the Scopes page, add: `https://www.googleapis.com/auth/drive.file`
5. Complete the remaining steps

**Step 3: Create OAuth Credentials**

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Desktop app** as the application type
4. Download the JSON credentials file

**Step 4: Generate Refresh Token**

Run the included helper script:

```bash
python get_gdrive_token.py path/to/credentials.json
```

This opens a browser for authentication and outputs your `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, and `GDRIVE_REFRESH_TOKEN`.

**Step 5: Create a Backup Folder**

1. Create a folder in [Google Drive](https://drive.google.com)
2. Copy the folder ID from the URL: `drive.google.com/drive/folders/FOLDER_ID`

</details>

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Branding (optional)
DASHBOARD_TITLE=Family Expenses

# Splitwise (required)
api_key=your_splitwise_api_key
group_id=your_group_id  # Optional: if omitted, fetches from ALL groups

# Google Drive (optional for local use)
GDRIVE_CLIENT_ID=your_client_id
GDRIVE_CLIENT_SECRET=your_client_secret
GDRIVE_REFRESH_TOKEN=your_refresh_token
GDRIVE_FOLDER_ID=your_folder_id

# Email (optional for local use)
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_password
RECIPIENT_EMAIL=recipient1@email.com,recipient2@email.com
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHBOARD_TITLE` | No | Custom title for the dashboard |
| `api_key` | **Yes** | Splitwise API Key |
| `group_id` | No | Splitwise Group ID (omit to fetch from all groups) |
| `GDRIVE_*` | No | Google Drive OAuth credentials |
| `GMAIL_*` | No | Gmail credentials for email automation |

### Command Reference

| Command | Description |
|---------|-------------|
| `python family_expenses.py` | Fetch data from Splitwise and upload to Google Drive |
| `python family_expenses.py --email` | Same as above, plus send an email report |
| `python family_expenses.py --local` | Generate dashboard locally using cached data (no API calls if cache exists) |
| `python family_expenses.py --no-upload` | Generate dashboard without uploading to Google Drive |
| `python family_expenses.py --full-log` | Enable verbose logging for troubleshooting |

You can combine flags: `python family_expenses.py --local --full-log`

### Local Mode (`--local`)

The `--local` flag generates a dashboard without uploading to Google Drive. It uses cached data when available to minimize API calls.

**Data source priority:**

1. Google Drive cache (most recent `*_expenses.json`)
2. Local `output/` folder cache
3. Splitwise API (only if no cache exists)

**Output files** are saved to `output/` with a date prefix:

```
output/
├── 2025-12-15_expenses.json
├── 2025-12-15_expenses.csv
└── 2025-12-15_expenses_dashboard.html
```

Files with the same date are automatically replaced.

---

## GitHub Actions Automation

This repository includes a GitHub Actions workflow that runs automatically on the 1st of each month at 8:00 AM CET.

**What the workflow does:**

1. Fetches all expenses from Splitwise
2. Generates an updated dashboard with monthly statistics
3. Uploads backup files (JSON, CSV, HTML) to Google Drive
4. Shares the dashboard with configured recipients
5. Sends an email report with spending summary and trends

### Running Manually

You can trigger the workflow at any time:

1. Go to **Actions** → **Monthly Expense Report** → **Run workflow**
2. Configure options:
   - **Upload files to Google Drive** — enabled by default
   - **Send email notification** — enabled by default
3. Click **Run workflow**

> **Tip:** Disable email notifications when testing to avoid unnecessary emails.

### GitHub Secrets

Navigate to **Settings** → **Secrets and variables** → **Actions** → **Secrets** tab:

| Secret | Required | Description |
|--------|----------|-------------|
| `SPLITWISE_API_KEY` | Yes | Your Splitwise API Key |
| `SPLITWISE_GROUP_ID` | No | Splitwise Group ID (omit to fetch all groups) |
| `GMAIL_ADDRESS` | For email | Gmail sender address |
| `GMAIL_APP_PASSWORD` | For email | Gmail App Password (16 characters) |
| `GDRIVE_CLIENT_ID` | For backup | Google OAuth Client ID |
| `GDRIVE_CLIENT_SECRET` | For backup | Google OAuth Client Secret |
| `GDRIVE_REFRESH_TOKEN` | For backup | Google OAuth Refresh Token |
| `GDRIVE_FOLDER_ID` | For backup | Google Drive folder ID |

### GitHub Variables

Navigate to **Settings** → **Secrets and variables** → **Actions** → **Variables** tab:

| Variable | Required | Description |
|----------|----------|-------------|
| `RECIPIENT_EMAIL` | For email | Comma-separated email addresses |
| `DASHBOARD_TITLE` | No | Custom dashboard title |

---

## Output Files

Each run generates three files with a date prefix (e.g., `2025-12-15`):

| File | Description |
|------|-------------|
| `*_expenses.json` | Complete backup — all Splitwise records with full details |
| `*_expenses.csv` | Complete backup — same data in spreadsheet format |
| `*_expenses_dashboard.html` | Interactive dashboard — expenses only, optimized for visualization |

### What's Included

**JSON/CSV backups** contain all Splitwise data:
- Expenses and payment settlements
- Full record details: `id`, `description`, `cost`, `date`, `category`, `repayments`, `users`, etc.

**HTML dashboard** contains:
- Expenses only (payments excluded)
- Fields needed for charts and filtering: `date`, `description`, `cost`, `category_name`

### Monthly Statistics

The dashboard and email reports include:

| Metric | Description |
|--------|-------------|
| **Last Month Total** | Sum of expenses in the most recent complete month |
| **Monthly Average** | Average across all months (including months with no expenses) |
| **Trend** | Percentage change compared to your average |
| **Top Categories** | Highest spending categories with individual trends |

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Missing api_key environment variable" | Ensure `.env` exists and contains `api_key=YOUR_KEY`. Verify at [Splitwise Apps](https://secure.splitwise.com/apps). |
| "Email not configured" | All three variables required: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`. App password must be 16 characters. |
| "Failed to upload to Google Drive" | Verify all `GDRIVE_*` variables are set. Run `get_gdrive_token.py` to refresh expired tokens. |
| Dashboard shows no data | Check `group_id` is correct, or remove it to fetch from all groups. |

For detailed logs, run with `--full-log`:
```bash
python family_expenses.py --local --full-log
```

---

## Contributing

Contributions are welcome. Please open an issue to discuss changes before submitting a pull request.

## License

This project is provided as-is under the MIT License.
