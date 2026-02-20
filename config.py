"""
config.py - Central configuration for the Job Finder system.

All tunable parameters, keyword lists, schedule times, and system constants
live here so that no magic numbers are scattered across modules.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.resolve()
RESUME_PDF_PATH = BASE_DIR / "Pragati_Khekale_DS_GL.pdf"
JOBS_LOG_CSV = BASE_DIR / "jobs_log.csv"
EXECUTION_LOG = BASE_DIR / "execution_log.txt"
CREDENTIALS_JSON = BASE_DIR / "credentials.json"

# ---------------------------------------------------------------------------
# Matching threshold
# ---------------------------------------------------------------------------

MATCH_THRESHOLD_PCT = 72          # Minimum match % to include a job
MATCH_THRESHOLD = MATCH_THRESHOLD_PCT / 100.0  # 0.72 as a float

# ---------------------------------------------------------------------------
# Scheduler times  (Mon-Fri: 9 AM, 11:30 AM, 4:30 PM | Sunday: 8 PM)
# ---------------------------------------------------------------------------

SCHEDULE = [
    # (day_of_week, hour, minute)
    ("mon-fri", 9,  0),
    ("mon-fri", 11, 30),
    ("mon-fri", 16, 30),
    ("sun",     20, 0),
]

# ---------------------------------------------------------------------------
# Technical skills – data science focus
# ---------------------------------------------------------------------------

TECH_SKILLS = [
    # Languages
    "python", "r", "sql", "scala", "java", "julia", "bash", "shell",
    # ML / DL frameworks
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
    "xgboost", "lightgbm", "catboost", "huggingface", "transformers",
    # Data manipulation
    "pandas", "numpy", "scipy", "dask", "polars",
    # Visualisation
    "matplotlib", "seaborn", "plotly", "tableau", "power bi", "powerbi",
    "looker", "d3.js",
    # Big data / cloud
    "spark", "pyspark", "hadoop", "hive", "kafka", "airflow",
    "aws", "gcp", "azure", "s3", "ec2", "sagemaker", "databricks",
    "snowflake", "redshift", "bigquery",
    # Databases
    "postgresql", "mysql", "mongodb", "cassandra", "elasticsearch",
    "redis", "sqlite",
    # MLOps / DevOps
    "mlflow", "kubeflow", "docker", "kubernetes", "git", "github",
    "gitlab", "ci/cd", "jenkins", "terraform",
    # NLP
    "nlp", "natural language processing", "spacy", "nltk", "bert",
    "gpt", "llm", "rag", "langchain", "openai",
    # Statistics / math
    "statistics", "probability", "linear algebra", "calculus",
    "hypothesis testing", "a/b testing", "regression", "classification",
    "clustering", "time series", "forecasting", "bayesian",
    # Other DS tools
    "jupyter", "anaconda", "streamlit", "flask", "fastapi",
    "rest api", "graphql", "etl", "data pipeline", "feature engineering",
    "data wrangling", "eda", "exploratory data analysis",
]

# Normalised (lowercase, stripped) for fast lookup
TECH_SKILLS_SET = set(s.lower().strip() for s in TECH_SKILLS)

# ---------------------------------------------------------------------------
# Soft skills – commonly sought in DS job postings
# ---------------------------------------------------------------------------

SOFT_SKILLS = [
    "communication", "collaboration", "teamwork", "leadership",
    "problem solving", "problem-solving", "critical thinking",
    "analytical thinking", "attention to detail", "time management",
    "project management", "stakeholder management", "presentation",
    "mentoring", "cross-functional", "agile", "scrum",
]

SOFT_SKILLS_SET = set(s.lower().strip() for s in SOFT_SKILLS)

# ---------------------------------------------------------------------------
# MAANG companies (and common aliases)
# ---------------------------------------------------------------------------

MAANG_COMPANIES = {
    "meta": ["meta", "facebook", "instagram", "whatsapp", "oculus"],
    "apple": ["apple", "apple inc"],
    "amazon": ["amazon", "aws", "amazon web services", "amazon.com"],
    "netflix": ["netflix"],
    "google": ["google", "alphabet", "deepmind", "waymo", "youtube"],
    # Sometimes "Microsoft" is included in FAANG discussions; keep separate
}

# Flat set for quick text-search
MAANG_ALIASES = set()  # type: ignore
for aliases in MAANG_COMPANIES.values():
    MAANG_ALIASES.update(a.lower() for a in aliases)

# ---------------------------------------------------------------------------
# Fortune 500 subset – representative companies that hire DS roles
# (Full list would be 500 entries; this curated subset covers the majors)
# ---------------------------------------------------------------------------

FORTUNE_500_COMPANIES = [
    # Tech
    "apple", "amazon", "alphabet", "google", "microsoft", "meta",
    "facebook", "netflix", "intel", "ibm", "oracle", "salesforce",
    "dell", "hp", "hewlett packard", "qualcomm", "cisco", "broadcom",
    "nvidia", "amd",
    # Finance
    "jpmorgan", "jp morgan", "bank of america", "wells fargo",
    "goldman sachs", "morgan stanley", "citigroup", "citi",
    "american express", "visa", "mastercard", "paypal", "fidelity",
    "charles schwab", "blackrock", "vanguard", "capital one",
    # Healthcare
    "unitedhealth", "cvs health", "mckesson", "johnson & johnson",
    "abbvie", "pfizer", "merck", "eli lilly", "bristol myers squibb",
    "humana", "anthem", "cigna",
    # Retail / Consumer
    "walmart", "target", "costco", "home depot", "lowes", "kroger",
    "walgreens", "procter & gamble", "coca-cola", "pepsico", "nestle",
    # Industrial / Energy
    "exxon", "chevron", "shell", "bp", "conocophillips",
    "general electric", "ge", "boeing", "lockheed martin", "raytheon",
    "caterpillar", "honeywell", "3m",
    # Telecom / Media
    "at&t", "verizon", "comcast", "disney", "warner bros",
    "t-mobile", "charter",
    # Automotive
    "ford", "general motors", "gm", "tesla",
    # Consulting / Services
    "accenture", "deloitte", "kpmg", "pwc", "ernst & young", "ey",
    "mckinsey", "bain",
    # E-commerce / Logistics
    "fedex", "ups", "dhl", "uber", "lyft", "airbnb",
    # Other tech-adjacent
    "twitter", "linkedin", "snap", "spotify", "adobe", "workday",
    "servicenow", "palantir", "snowflake", "databricks", "stripe",
    "square", "block",
]

FORTUNE_500_SET = set(c.lower().strip() for c in FORTUNE_500_COMPANIES)

# ---------------------------------------------------------------------------
# H1B sponsorship detection keywords
# ---------------------------------------------------------------------------

H1B_POSITIVE_KEYWORDS = [
    "h1b", "h-1b", "h1-b", "will sponsor", "visa sponsorship",
    "sponsorship available", "open to sponsorship", "sponsor work visa",
    "employment authorization", "work authorization provided",
    "we sponsor", "sponsoring h1b", "ead accepted",
    "visa transfer", "h1b transfer",
]

H1B_NEGATIVE_KEYWORDS = [
    "no sponsorship", "not able to sponsor", "cannot sponsor",
    "sponsorship not available", "must be authorized",
    "must be eligible to work", "us citizens only",
    "us citizen or permanent resident", "green card only",
    "no h1b", "no visa", "no h-1b",
    "we are unable to sponsor", "unable to provide sponsorship",
    "does not sponsor",
]

# ---------------------------------------------------------------------------
# Application portal detection patterns
# ---------------------------------------------------------------------------

PORTAL_PATTERNS = {
    "Workday":    ["workday.com", "myworkdayjobs.com"],
    "Greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
    "Lever":      ["lever.co", "jobs.lever.co"],
    "Taleo":      ["taleo.net", "oraclecloud.com/hcmUI/CandidateExperience"],
    "iCIMS":      ["icims.com"],
    "SmartRecruiters": ["smartrecruiters.com"],
    "BambooHR":   ["bamboohr.com"],
    "Jobvite":    ["jobvite.com"],
    "ADP":        ["adp.com", "workforcenow.adp.com"],
    "SAP SuccessFactors": ["successfactors.com", "sapsf.com"],
    "LinkedIn Easy Apply": ["linkedin.com/jobs"],
    "Indeed":     ["indeed.com/apply", "indeed.com/viewjob"],
}

# ---------------------------------------------------------------------------
# Google Sheets configuration
# ---------------------------------------------------------------------------

SHEET_NAME = "Job Finder Results"

# Column order in the sheet (must match what drive_uploader writes)
SHEET_COLUMNS = [
    "Date",
    "Job Title",
    "Company",
    "Match %",
    "H1B Sponsor",
    "MAANG",
    "Fortune 500",
    "Job URL",
    "Application Portal",
    "Key Skills Matched",
    "ATS Keywords",
    "Location",
    "Source",
    "Posted Date",
]

# Column letters for conditional formatting (1-indexed in Sheets API)
COL_H1B      = 5   # "H1B Sponsor"
COL_MAANG    = 6   # "MAANG"
COL_F500     = 7   # "Fortune 500"
COL_MATCH    = 4   # "Match %"

# Colours for conditional formatting
COLOR_GREEN = {"red": 0.57, "green": 0.82, "blue": 0.58}  # #92D050
COLOR_RED   = {"red": 0.96, "green": 0.49, "blue": 0.49}  # #F57F7F
COLOR_YELLOW= {"red": 1.0,  "green": 0.93, "blue": 0.60}  # #FEE08B  (mid match)
COLOR_TEAL  = {"red": 0.40, "green": 0.80, "blue": 0.80}  # high match

# ---------------------------------------------------------------------------
# Email / SMTP configuration (read from environment)
# ---------------------------------------------------------------------------

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_TO     = os.getenv("NOTIFY_TO", "")       # comma-separated recipients

# ---------------------------------------------------------------------------
# Job scraping configuration
# ---------------------------------------------------------------------------

# Max jobs to retrieve per scraping run (per source)
MAX_JOBS_PER_SOURCE = 50
SCRAPE_DELAY_SECONDS = 2          # polite delay between requests
REQUEST_TIMEOUT = 15              # seconds

# Demo / mock mode – set DEMO_MODE=true in .env to skip real scraping
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

# Search queries for job scraping
JOB_SEARCH_QUERIES = [
    "data scientist",
    "machine learning engineer",
    "ml engineer",
    "data science",
    "senior data scientist",
]

JOB_LOCATIONS = ["United States", "Remote"]

# ---------------------------------------------------------------------------
# Google Sheets / Drive
# ---------------------------------------------------------------------------

GOOGLE_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Spreadsheet ID – set via env or leave blank to auto-create
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

# ---------------------------------------------------------------------------
# User-agent for HTTP requests
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}
