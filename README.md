# Splitwise Expense Dashboard

A self-hosted application to track expenses from Splitwise, visualize them in an interactive dashboard, and receive automated reports via email.

> **Customizable**: Configure the dashboard title via the `DASHBOARD_TITLE` environment variable.

---

## Quick Start (Template Users)

If you're setting up this project from the template, follow these steps:

### 1. Create Your Repository

You should see the "Create a new repository" form. Fill in:
- **Repository name**: Choose a name (e.g., `my-expenses`)
- **Description**: (Optional) Add a description
- **Public/Private**: Choose your preferred visibility

Click **"Create repository"** to create your copy.

### 2. Clone Your New Repository

```bash
git clone https://github.com/YOUR_USERNAME/your-repo-name.git
cd your-repo-name
```

### 3. Set Up Python Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r Requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see [Prerequisites](#prerequisites) for how to obtain them):

```env
# Required
api_key=YOUR_SPLITWISE_API_KEY

# Optional
group_id=YOUR_GROUP_ID
DASHBOARD_TITLE=My Family Expenses
```

### 5. Test Locally

```bash
python family_expenses.py --local
open output/*_expenses_dashboard.html
```

You should see your expenses in an interactive dashboard!

---

## Features

- **Interactive Dashboard**: Monthly and category charts, dynamic filters, and search
- **Complete Backup**: JSON and CSV with all Splitwise data (including payments, users, repayments)
- **Full History**: Retrieves ALL expenses from first to last via automatic pagination
- **Rich Email Reports**: Monthly summary with trends, top categories, and Google Drive link (no attachment)
- **Google Drive Backup**: Automatic cloud storage with file sharing to recipients
- **Data Export**: Download all data in CSV format from the dashboard

---

## Project Structure

```
family_expenses/
├── family_expenses.py      # CLI entry point
├── src/
│   ├── config.py           # Configuration and env vars
│   ├── splitwise_client.py # Splitwise API client
│   ├── dashboard.py        # Dashboard generation
│   ├── email_sender.py     # Email sending (with summary)
│   ├── gdrive.py           # Google Drive upload & sharing
│   └── stats.py            # Monthly statistics & trends
├── templates/
│   └── dashboard.html      # Jinja2 template
├── Requirements.txt
└── .github/workflows/
    └── expense_report.yml  # GitHub Actions automation
```

---

## Prerequisites

Before using this application, you need to obtain credentials for the services you want to use.

### Splitwise API Key (Required)

<details>
<summary><strong>Click to expand: How to get your Splitwise API Key</strong></summary>

1. Go to [https://secure.splitwise.com/apps](https://secure.splitwise.com/apps)
2. Click **"Register your application"**
3. Fill in the form:
   - **Application name**: `Expense Dashboard` (or any name)
   - **Description**: `Personal expense tracking`
   - **Homepage URL**: `https://github.com` (or any URL)
4. Click **"Register and get API key"**
5. Copy the **API Key** (not the Consumer Key/Secret)

**Find your Group ID** (optional):
- Open Splitwise in your browser
- Go to your group
- The URL will be: `https://www.splitwise.com/groups/XXXXXXX`
- The number `XXXXXXX` is your Group ID

</details>

### Gmail App Password (For Email Automation)

<details>
<summary><strong>Click to expand: How to create a Gmail App Password</strong></summary>

> **Note**: You must have 2-Step Verification enabled on your Google Account.

1. Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "Signing in to Google", click **"2-Step Verification"**
3. Scroll to the bottom and click **"App passwords"**
4. Select app: **"Mail"**
5. Select device: **"Other (Custom name)"** → Enter `Expense Dashboard`
6. Click **"Generate"**
7. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

**Important**: Store this password securely - you won't be able to see it again!

</details>

### Google Drive OAuth (For Cloud Backup)

<details>
<summary><strong>Click to expand: How to set up Google Drive OAuth</strong></summary>

#### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Go to **APIs & Services** → **Library**
4. Search for **"Google Drive API"** and enable it

#### Step 2: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **"External"** user type
3. Fill in required fields:
   - App name: `Expense Dashboard`
   - User support email: Your email
   - Developer contact: Your email
4. Click **"Save and Continue"**
5. On Scopes page, click **"Add or Remove Scopes"**
6. Search and add: `https://www.googleapis.com/auth/drive.file`
7. Save and continue through the remaining steps

#### Step 3: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. Application type: **"Desktop app"**
4. Name: `Expense Dashboard`
5. Click **"Create"**
6. Download the JSON file

#### Step 4: Get Refresh Token

Run the helper script included in this project:

```bash
python get_gdrive_token.py path/to/downloaded-credentials.json
```

This will:
1. Open a browser for authentication
2. Print your `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, and `GDRIVE_REFRESH_TOKEN`

#### Step 5: Create a Google Drive Folder

1. Go to [Google Drive](https://drive.google.com)
2. Create a new folder for your backups
3. Open the folder
4. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID`

</details>

---

## Local Setup

### Environment Variables

Create a `.env` file with the following variables:

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

### Usage

```bash
# Generate dashboard and upload to Google Drive
python family_expenses.py

# Generate dashboard and send email
python family_expenses.py --email

# Generate dashboard without Drive upload (uses temp files)
python family_expenses.py --no-upload

# Generate dashboard locally in output/ folder (for testing)
python family_expenses.py --local
```

With `--local`, files are saved to `output/` and you can open the dashboard in your browser:

```bash
open output/2025-12-15_expenses_dashboard.html
```

---

## GitHub Actions Automation

This project includes a GitHub workflow that automatically runs the script:

- **When**: 1st of each month at 8:00 AM CET
- **Command**: `python family_expenses.py --email`
- **What it does**:
  1. Fetches expenses from Splitwise
  2. Generates the updated dashboard with monthly summary
  3. Uploads files (JSON, CSV, HTML) to Google Drive
  4. Shares the dashboard with email recipients
  5. Sends an email with:
     - Monthly summary (total expenses, trends vs average)
     - Top categories with individual trends
     - Google Drive link to the full dashboard (no attachment)

### Manual Execution

You can run the workflow manually from GitHub Actions with configurable options:

1. Go to **Actions** → **Monthly Expense Report** → **Run workflow**
2. Configure options:
   - **Upload files to Google Drive**: ✅ enabled by default
   - **Send email notification**: ✅ enabled by default
3. Click **Run workflow**

Useful for testing: disable "Send email" to verify only the Drive upload.

### GitHub Secrets Configuration

Add these secrets in your repository settings (Settings → Secrets and variables → Actions → **Secrets** tab):

| Secret | Description |
|--------|-------------|
| `SPLITWISE_API_KEY` | Your Splitwise API Key |
| `SPLITWISE_GROUP_ID` | (Optional) Splitwise Group ID |
| `GMAIL_ADDRESS` | Your Gmail sender address |
| `GMAIL_APP_PASSWORD` | Gmail App Password (16 characters) |
| `GDRIVE_CLIENT_ID` | Google OAuth Client ID |
| `GDRIVE_CLIENT_SECRET` | Google OAuth Client Secret |
| `GDRIVE_REFRESH_TOKEN` | Google OAuth Refresh Token |
| `GDRIVE_FOLDER_ID` | Google Drive folder ID for backups |

### GitHub Variables Configuration

Add these variables (Settings → Secrets and variables → Actions → **Variables** tab):

| Variable | Description |
|----------|-------------|
| `RECIPIENT_EMAIL` | Comma-separated recipient emails (e.g., `email1@gmail.com,email2@gmail.com`) |
| `DASHBOARD_TITLE` | (Optional) Custom dashboard title |

---

## Output Files

Files are uploaded to Google Drive (no local storage by default):

| File | Contents |
|------|----------|
| `YYYY-MM-DD_expenses.json` | **Complete backup**: all Splitwise records with all fields (category, users, repayments, etc.) |
| `YYYY-MM-DD_expenses.csv` | **Complete backup**: same data in tabular format |
| `YYYY-MM-DD_expenses_dashboard.html` | **Dashboard**: expenses only (no payments), selected fields for visualization |

### Data Structure

**JSON/CSV (complete backup)** includes:
- All records (expenses + payments/settlements)
- All Splitwise fields: `id`, `description`, `cost`, `date`, `category`, `repayments`, `users`, `created_by`, `receipt`, etc.
- Fully deserialized nested objects (e.g., `category: {id, name, subcategories}`)

**HTML (dashboard)** includes only:
- Expenses (excluding payments)
- Fields for visualization: `id`, `description`, `cost`, `currency_code`, `date`, `category_name`

### Monthly Summary & Statistics

The dashboard and email include a monthly summary section with:

- **Last Month's Total**: Sum of all expenses in the most recent complete month
- **Monthly Average**: Calculated using ALL months between first and last expense (even empty months)
- **Trend**: Percentage comparison of last month vs the average
- **Top Categories**: Highest spending categories with individual trend percentages

---

## Troubleshooting

### "Missing api_key environment variable"
- Ensure your `.env` file exists and contains `api_key=YOUR_KEY`
- Verify the API key is correct at [Splitwise Apps](https://secure.splitwise.com/apps)

### "Email not configured"
- All three variables are required: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`
- Make sure the app password is 16 characters (no spaces)

### "Failed to upload to Google Drive"
- Verify all four `GDRIVE_*` variables are set
- Run `get_gdrive_token.py` again to refresh the token if expired

### Dashboard shows no data
- Check that `group_id` is correct (or remove it to fetch all groups)
- Verify your Splitwise account has expenses in the specified group

---

## License

This project is provided as-is for personal use.
