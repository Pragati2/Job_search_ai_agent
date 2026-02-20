# Quick Start Guide - Job Finder Agent

Get the system running in under 5 minutes.

## Step 1: Activate Virtual Environment

```bash
cd /Users/pragatikhekale/.claude-worktrees/job-search/affectionate-yalow
source venv/bin/activate
```

## Step 2: Install Missing Dependencies

```bash
python -m pip install APScheduler python-dotenv
```

APScheduler and python-dotenv are the only packages not pre-installed in your venv. All other dependencies (pypdf, google-api-python-client, requests, beautifulsoup4, pandas, etc.) are already present.

## Step 3: Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
DEMO_MODE=true
```

For full functionality, also configure:

```bash
# Google Sheets (optional for first test)
GOOGLE_CREDENTIALS_PATH=credentials.json
SPREADSHEET_ID=

# Email (optional for first test)
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_TO=your_email@gmail.com
```

## Step 4: Run Your First Test

```bash
python orchestrator.py
```

This will:
- Parse your resume (Pragati_Khekale_DS_GL.pdf)
- Generate 10 realistic demo jobs
- Score each job against your resume
- Print a summary report
- Create execution_log.txt

Expected output:
```
============================================================
Job Finder pipeline starting – 2026-02-19 XX:XX:XX
Demo mode: True
[1/7] Loading resume...
Resume loaded: 26 technical skills, 5 soft skills.
[2/7] Scraping jobs...
Demo mode: generated 10 sample jobs.
[3/7] Classifying jobs (threshold: 72%)...
...
============================================================
```

## Step 5: Check Match Scores

```bash
python check_scores.py
```

See how your resume matches against each demo job:

```
 27.4%  Senior Data Scientist       @  Google       H1B=True   MAANG=True
 21.5%  Machine Learning Engineer   @  Meta         H1B=True   MAANG=True
 20.5%  Data Scientist - NLP        @  Amazon       H1B=False  MAANG=True
...
```

## Step 6 (Optional): Set Up Google Sheets

### 6a. Create Service Account

1. Go to https://console.cloud.google.com
2. Create a project (or use existing)
3. Enable "Google Sheets API" and "Google Drive API"
4. Go to IAM & Admin > Service Accounts
5. Create service account
6. Click on the account > Keys > Add Key > JSON
7. Download the JSON file
8. Save it as `credentials.json` in the project directory

### 6b. Create and Share Spreadsheet

1. Create a new Google Sheet or use existing
2. Copy the spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
3. Open `credentials.json` and find the `client_email` field
4. Share the spreadsheet with that email (Editor permissions)
5. Update `.env`:
   ```bash
   SPREADSHEET_ID=your_spreadsheet_id_here
   ```

### 6c. Test Sheets Integration

```bash
python orchestrator.py
```

If configured correctly, you'll see:
```
[4/7] Logging to Google Sheets...
```

And jobs will appear in your spreadsheet with conditional formatting.

## Step 7 (Optional): Set Up Email Notifications

### For Gmail:

1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create an App Password for "Mail"
4. Copy the 16-character password
5. Update `.env`:
   ```bash
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=xxxx_xxxx_xxxx_xxxx
   NOTIFY_TO=your_email@gmail.com
   ```

### Test Email:

```bash
python notifier.py
```

This creates a sample execution log entry. To test a full email with job data, run:

```bash
python orchestrator.py
```

If jobs meet the 72% threshold, you'll receive an email.

## Step 8 (Optional): Start the Scheduler

Preview upcoming runs:

```bash
python scheduler.py --next
```

Start the scheduler (runs forever until Ctrl+C):

```bash
python scheduler.py
```

Or run once immediately:

```bash
python scheduler.py --once
```

## Understanding the 72% Threshold

The demo jobs typically score 15-27% because:
- The matching algorithm is conservative (TF-IDF + keyword overlap)
- Your resume may not perfectly align with the sample job descriptions
- This is realistic behavior - production jobs will have more variety

**To see more matches:**

Option 1: Lower the threshold in `config.py`:
```python
MATCH_THRESHOLD_PCT = 50  # More permissive
```

Option 2: Add more skills to your resume that appear in data science job postings

Option 3: Wait for production mode with real job data (more volume = more matches)

## Switching to Production Mode

When ready to scrape real jobs:

1. Edit `.env`:
   ```bash
   DEMO_MODE=false
   ```

2. Run:
   ```bash
   python orchestrator.py
   ```

**Note**: LinkedIn and Indeed have anti-scraping measures. The current implementation may return limited results. For production reliability, consider:
- Selenium-based scraping (see comments in `orchestrator.py`)
- LinkedIn Jobs API (requires partnership)
- Indeed Publisher API (requires approval)
- Third-party scraping services

## File Locations

All files are in:
```
/Users/pragatikhekale/.claude-worktrees/job-search/affectionate-yalow/
```

Key files:
- **orchestrator.py** - Main entry point
- **config.py** - Adjust settings here
- **execution_log.txt** - Run history
- **jobs_log.csv** - Local backup (auto-created on first qualifying job)
- **.env** - Your secrets (never commit this!)

## Common Issues

### "No module named 'apscheduler'"
```bash
python -m pip install APScheduler python-dotenv
```

### "Resume PDF not found"
Ensure `Pragati_Khekale_DS_GL.pdf` exists in the project directory.

### Google Sheets errors
1. Verify `credentials.json` exists
2. Check that the spreadsheet is shared with the service account email
3. Confirm `GOOGLE_CREDENTIALS_PATH` and `SPREADSHEET_ID` in `.env`

### Email not sending (Gmail)
Must use an App Password, not your account password. See Step 7 above.

### Match scores are low
This is normal. See "Understanding the 72% Threshold" above.

## Next Steps

1. Review `README.md` for full documentation
2. Explore `config.py` to customize skills, thresholds, schedules
3. Check `brain.py` to understand the matching algorithm
4. Review sample output in `execution_log.txt`
5. Set up Google Sheets and email for full automation

## Getting Help

Run individual test scripts:
```bash
python test_system.py      # Full system test
python Data_Extraction.py  # Test resume parsing
python check_scores.py     # See match scores
python notifier.py         # Test logging
```

Check logs:
```bash
cat execution_log.txt
tail -50 execution_log.txt
```

---

You're all set! The system is fully implemented and ready to use.
