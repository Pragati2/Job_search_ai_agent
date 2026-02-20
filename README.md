# Job Finder Agent

An intelligent, automated job search system for data science positions. This system scrapes job postings from multiple sources, uses NLP-based matching to score candidates against your resume, classifies jobs by key attributes (H1B sponsorship, MAANG companies, Fortune 500), and automatically logs qualified matches to Google Sheets while sending email notifications.

## Features

- **Resume Parsing**: Extracts skills, experience, and keywords from PDF resumes
- **Intelligent Matching**: TF-IDF cosine similarity + keyword overlap scoring (0-100%)
- **H1B Detection**: Identifies visa sponsorship signals in job descriptions
- **Company Classification**: Detects MAANG companies and Fortune 500 organizations
- **ATS Portal Detection**: Identifies application platforms (Workday, Greenhouse, Lever, etc.)
- **ATS Keyword Extraction**: Suggests keywords to optimize your resume for each job
- **Google Sheets Integration**: Logs results with conditional formatting and duplicate detection
- **Email Notifications**: HTML email reports with top matches and ATS tips
- **Local CSV Backup**: Maintains a local jobs_log.csv for offline access
- **Automated Scheduling**: Runs Mon-Fri at 9 AM, 11:30 AM, 4:30 PM + Sunday 8 PM
- **Demo Mode**: Test the system end-to-end with realistic sample jobs

## Project Structure

```
affectionate-yalow/
├── Data_Extraction.py      # PDF resume parsing and keyword extraction
├── brain.py                # Core NLP matching and classification logic
├── drive_uploader.py       # Google Sheets API integration
├── notifier.py             # Email notifications and execution logging
├── orchestrator.py         # Main pipeline workflow controller
├── scheduler.py            # APScheduler job trigger system
├── config.py               # Central configuration (skills, thresholds, etc.)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── Pragati_Khekale_DS_GL.pdf  # Your resume
├── jobs_log.csv            # Local CSV backup (auto-created)
├── execution_log.txt       # Run history log (auto-created)
└── credentials.json        # Google service account key (you provide)
```

## Installation

### 1. Activate the Virtual Environment

```bash
cd /Users/pragatikhekale/.claude-worktrees/job-search/affectionate-yalow
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages:
- `pypdf` for resume parsing
- `google-api-python-client` for Sheets integration
- `APScheduler` for job scheduling
- `beautifulsoup4` + `requests` for web scraping
- `python-dotenv` for environment config

### 3. Configure Environment Variables

Copy the example .env file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Demo mode (use sample jobs, no real scraping)
DEMO_MODE=true

# Google Sheets (see Google Setup below)
GOOGLE_CREDENTIALS_PATH=credentials.json
SPREADSHEET_ID=

# Email notifications (Gmail example)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
NOTIFY_TO=your_email@gmail.com
```

### 4. Google Sheets Setup

**Create a service account:**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable **Google Sheets API** and **Google Drive API**
4. Navigate to **IAM & Admin > Service Accounts**
5. Create a service account and download the JSON key file
6. Save the key file as `credentials.json` in the project directory

**Share your spreadsheet:**

1. Create a Google Sheet or leave `SPREADSHEET_ID` blank to auto-create
2. Open the JSON key file and find the `client_email` field
3. Share your Google Sheet with this email address (Editor permissions)

### 5. Gmail App Password (for notifications)

If using Gmail for notifications:

1. Enable [2-Factor Authentication](https://myaccount.google.com/security)
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate an app password for "Mail"
4. Use the 16-character password in your `.env` file as `SMTP_PASSWORD`

## Usage

### Quick Test (Demo Mode)

Run the pipeline once with sample jobs:

```bash
python orchestrator.py
```

This will:
- Parse your resume
- Generate 10 realistic demo jobs
- Classify and score each job
- Log results to Google Sheets (if configured)
- Save local CSV backup
- Print a summary report

### Check Match Scores

```bash
python check_scores.py
```

See the match percentage for each demo job to understand how the scoring works.

### Test Individual Components

```bash
# Test resume extraction
python Data_Extraction.py Pragati_Khekale_DS_GL.pdf

# Test execution logging
python notifier.py

# Run full system test
python test_system.py
```

### Production Mode

Edit `.env` and set `DEMO_MODE=false` to enable real job scraping from Indeed and LinkedIn.

**Note**: LinkedIn and Indeed have anti-scraping measures. The current implementation uses `requests` + `BeautifulSoup`. For production reliability, integrate Selenium with headless Chrome (see comments in `orchestrator.py`).

### Scheduled Runs

Start the scheduler daemon:

```bash
python scheduler.py
```

This runs the pipeline on the configured schedule:
- **Monday – Friday**: 9:00 AM, 11:30 AM, 4:30 PM
- **Sunday**: 8:00 PM

Press `Ctrl+C` to stop the scheduler.

**Other scheduler options:**

```bash
# Run once immediately and exit
python scheduler.py --once

# Show next 5 scheduled run times
python scheduler.py --next
```

## Configuration

All tunable settings live in `config.py`:

### Match Threshold

```python
MATCH_THRESHOLD_PCT = 72  # Minimum match % to include a job
```

Jobs scoring below this are filtered out. Adjust based on your preferences:
- **50-60%**: More permissive, catches broader matches
- **72%** (default): Balanced, high-quality matches
- **80-90%**: Very strict, only near-perfect fits

### Technical Skills

Add skills relevant to your background:

```python
TECH_SKILLS = [
    "python", "sql", "tensorflow", "pytorch", ...
]
```

### Schedule Times

Modify the `SCHEDULE` list to change run times:

```python
SCHEDULE = [
    ("mon-fri", 9,  0),    # Weekday 9 AM
    ("mon-fri", 11, 30),   # Weekday 11:30 AM
    ("mon-fri", 16, 30),   # Weekday 4:30 PM
    ("sun",     20, 0),    # Sunday 8 PM
]
```

## Google Sheets Output

The system logs jobs to a Google Sheet with these columns:

| Date | Job Title | Company | Match % | H1B Sponsor | MAANG | Fortune 500 | Job URL | Application Portal | Key Skills Matched | ATS Keywords | Location | Source | Posted Date |
|------|-----------|---------|---------|-------------|-------|-------------|---------|-------------------|-------------------|--------------|----------|--------|-------------|

**Conditional formatting:**
- **Green cells**: TRUE values (H1B sponsor available, MAANG, Fortune 500)
- **Red cells**: FALSE values (no sponsorship, etc.)
- **Color gradient**: Match % column (red → yellow → teal)

**Duplicate detection**: Jobs are identified by `Company + Job Title` to prevent duplicates across runs.

## Email Notifications

When qualifying jobs are found, you receive an HTML email with:

- Summary table of matched jobs
- H1B sponsorship status badges
- MAANG / Fortune 500 indicators
- ATS keyword suggestions for top 5 jobs
- Direct links to job postings

## Local CSV Backup

All qualified jobs are appended to `jobs_log.csv` for offline analysis. This file is created automatically on first run.

## Execution Log

Every run is logged to `execution_log.txt` with:
- Run timestamp
- Total jobs scraped
- Qualified jobs count
- Logged to Sheets count
- Email sent status
- Duration
- Top matches
- Errors (if any)

## How the Matching Algorithm Works

The match score combines two signals:

1. **TF-IDF Cosine Similarity** (65% weight)
   - Compares your full resume text against the job description
   - Captures semantic similarity and context

2. **Keyword Overlap Ratio** (35% weight)
   - Counts how many of your extracted skills appear in the job posting
   - Rewards explicit skill matches (important for ATS systems)

**Formula:**
```
match_score = 0.65 × cosine_similarity + 0.35 × skill_overlap_ratio
```

This is converted to a percentage (0-100%) for readability.

## Job Scraping Sources

### Current Support

- **Indeed**: Uses public job search API (limited)
- **LinkedIn**: Public /jobs/search endpoint (anti-bot measures apply)

### Production Recommendations

For reliable production scraping:

1. **Selenium + headless Chrome**: Bypass basic anti-bot checks
2. **Indeed Publisher API**: Requires approval but provides official access
3. **LinkedIn Jobs API**: Requires partnership
4. **Third-party APIs**: ScraperAPI, BrightData, or similar services

See `orchestrator.py` comments for integration points.

## Classification Logic

### H1B Sponsorship Detection

**Positive signals** (returns `True`):
- "h1b", "h-1b", "will sponsor", "visa sponsorship", "we sponsor", etc.

**Negative signals** (returns `False`):
- "no sponsorship", "cannot sponsor", "us citizens only", etc.

**Unknown** (returns `None`):
- No sponsorship mentions found

### MAANG Detection

Checks company name and job text for:
- Meta, Facebook, Instagram, WhatsApp, Oculus
- Apple, Apple Inc
- Amazon, AWS, Amazon Web Services
- Netflix
- Google, Alphabet, DeepMind, Waymo, YouTube

### Fortune 500

Matches against a curated list of ~111 major companies (tech, finance, healthcare, retail, etc.). See `config.py` for the full list.

### Application Portal Detection

Identifies ATS platforms:
- Workday, Greenhouse, Lever, Taleo, iCIMS, SmartRecruiters, BambooHR, Jobvite, ADP, SAP SuccessFactors, LinkedIn Easy Apply, Indeed

## Troubleshooting

### No jobs logged to Google Sheets

1. Verify `credentials.json` exists and is valid
2. Check that the spreadsheet is shared with the service account email
3. Look for errors in execution_log.txt
4. Test with: `python -c "from drive_uploader import log_jobs_to_sheet; print('OK')"`

### Email notifications not sending

1. Confirm SMTP credentials are correct
2. For Gmail, ensure you're using an **App Password**, not your account password
3. Check that 2FA is enabled on your Google account
4. Test with: `python notifier.py`

### Match scores too low

1. Lower `MATCH_THRESHOLD_PCT` in `config.py` (try 50-60%)
2. Add more skills to your resume that appear in target jobs
3. Check `python check_scores.py` to see actual scores
4. Review the ATS keywords suggestions - add missing skills to your resume

### Python version warnings

The venv uses Python 3.9.7, which is past end-of-life. The code works but you may see warnings from google-auth. To update:

```bash
# Create a new venv with Python 3.11+
python3.11 -m venv venv_new
source venv_new/bin/activate
pip install -r requirements.txt
```

### "No qualifying jobs" in demo mode

This is expected - the demo jobs are scored against your resume and may not reach the 72% threshold. This is realistic behavior. In production mode with real job data, you'll see more variety.

## Customization

### Add More Job Sources

Edit `orchestrator.py` and add scraper functions for Glassdoor, AngelList, etc. Follow the pattern of `_scrape_indeed()` and `_scrape_linkedin()`.

### Adjust Scoring Weights

In `brain.py`, modify the `calculate_match_score()` function:

```python
def calculate_match_score(
    resume_profile: dict,
    job_text: str,
    alpha: float = 0.65,   # TF-IDF weight
    beta: float = 0.35,    # Keyword overlap weight
) -> float:
```

### Add Custom Classifications

Extend `classify_job()` in `brain.py` to add new fields (e.g., remote-friendly detection, salary range extraction).

### Change Notification Format

Edit `_build_html_body()` and `_build_plain_body()` in `notifier.py` to customize email templates.

## Security Notes

- **Never commit `.env` or `credentials.json` to version control**
- Add them to `.gitignore`:
  ```
  .env
  credentials.json
  jobs_log.csv
  execution_log.txt
  ```
- Use environment-specific credentials for production deployments
- Rotate service account keys periodically

## License

This project is for personal use. Respect the terms of service of job boards when scraping.

## Support

For issues or questions, check:
- Execution log: `execution_log.txt`
- Python logs: Run with `python -u orchestrator.py 2>&1 | tee run.log`
- Test individual modules with their `if __name__ == "__main__"` blocks

---

**Built with Claude Code** | Last updated: 2026-02-19
