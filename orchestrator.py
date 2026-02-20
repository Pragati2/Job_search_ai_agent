"""
orchestrator.py - Main workflow controller for the Job Finder system.

Coordinates the full pipeline:
  1. Load and parse the resume PDF
  2. Scrape jobs from LinkedIn / Indeed / Glassdoor (or mock data in demo mode)
  3. Classify each job via brain.py (match score, H1B, MAANG, F500, portal)
  4. Filter to jobs meeting the 72% threshold
  5. Log results to Google Sheets via drive_uploader.py
  6. Save a local CSV backup (jobs_log.csv)
  7. Send email notifications via notifier.py
  8. Write an execution record to execution_log.txt

Entry point:
  run_pipeline()     - Executes the full pipeline once
  run_once()         - Alias; called by scheduler.py on each trigger

Scraping strategy:
  - In DEMO_MODE (default) a set of realistic sample jobs is generated so the
    system can be tested end-to-end without real HTTP calls.
  - In production mode the scraper makes real requests to job boards.
    NOTE: LinkedIn, Indeed and Glassdoor have anti-scraping measures;
    a Selenium-based headless approach is more reliable than raw requests.
    The production scraper below uses requests + BeautifulSoup for Indeed
    and notes where Selenium integration would be inserted.
"""

import csv
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import (
    RESUME_PDF_PATH,
    JOBS_LOG_CSV,
    MATCH_THRESHOLD_PCT,
    DEMO_MODE,
    MAX_JOBS_PER_SOURCE,
    SCRAPE_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    JOB_SEARCH_QUERIES,
    JOB_LOCATIONS,
    REQUEST_HEADERS,
)
from Data_Extraction import load_resume
from brain import classify_jobs_batch
from notifier import notify_high_match_jobs, log_execution, build_run_summary

logger = logging.getLogger(__name__)

# Optional: import SheetsLogger only if credentials exist
try:
    from drive_uploader import log_jobs_to_sheet
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    logger.warning("drive_uploader import failed – Google Sheets logging disabled.")


# ---------------------------------------------------------------------------
# Demo / mock job data
# ---------------------------------------------------------------------------

_DEMO_JOBS = [
    {
        "title": "Senior Data Scientist",
        "company": "Google",
        "location": "Mountain View, CA (Remote)",
        "url": "https://careers.google.com/jobs/example-ds-001",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "We are looking for a Senior Data Scientist to join our Search team. "
            "You will build machine learning models using Python, TensorFlow, and PyTorch. "
            "Strong background in statistics, SQL, and data visualization required. "
            "Experience with BigQuery, Spark, and distributed systems is a plus. "
            "You will collaborate cross-functionally with engineering and product teams. "
            "PhD or Master's in Computer Science, Statistics, or related field preferred. "
            "5+ years of experience in data science or machine learning. "
            "We welcome candidates requiring H1B visa sponsorship."
        ),
    },
    {
        "title": "Machine Learning Engineer",
        "company": "Meta",
        "location": "Menlo Park, CA",
        "url": "https://www.metacareers.com/jobs/example-mle-002",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Meta is seeking a Machine Learning Engineer for the Ads ranking team. "
            "Responsibilities include developing scalable ML pipelines using PyTorch, "
            "conducting A/B testing, and deploying models to production. "
            "Required: Python, SQL, deep learning, feature engineering. "
            "Experience with MLflow, Docker, Kubernetes is highly desired. "
            "Strong analytical skills and attention to detail. "
            "Visa sponsorship available for qualified candidates."
        ),
    },
    {
        "title": "Data Scientist - NLP",
        "company": "Amazon",
        "location": "Seattle, WA",
        "url": "https://www.amazon.jobs/en/jobs/example-nlp-003",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Amazon Alexa team is hiring a Data Scientist specializing in NLP. "
            "You will work on natural language understanding, BERT fine-tuning, "
            "and conversational AI. Python, PyTorch, Hugging Face transformers required. "
            "Experience with AWS SageMaker, S3, and EMR is essential. "
            "Statistical modelling, hypothesis testing, and experimentation skills needed. "
            "We are not able to sponsor work visas at this time."
        ),
    },
    {
        "title": "Applied Scientist II",
        "company": "Microsoft",
        "location": "Redmond, WA (Hybrid)",
        "url": "https://careers.microsoft.com/jobs/example-as-004",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Microsoft Azure AI team seeks an Applied Scientist. "
            "You will design and implement forecasting models, anomaly detection systems, "
            "and causal inference frameworks. Required: Python, R, statistics, time series. "
            "Experience with Azure ML, MLOps, and large-scale data processing. "
            "Publications in top ML venues (NeurIPS, ICML, ICLR) are a plus. "
            "Open to H1B sponsorship and H1B transfer."
        ),
    },
    {
        "title": "Data Analyst",
        "company": "Netflix",
        "location": "Los Gatos, CA",
        "url": "https://jobs.netflix.com/jobs/example-da-005",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Netflix is looking for a Data Analyst on the Content Strategy team. "
            "You will analyze viewer behaviour using SQL, Python, and Tableau. "
            "Build dashboards and reports in Looker. A/B testing and experiment design. "
            "Strong communication and presentation skills. "
            "2+ years of experience in analytics. Must be eligible to work in the US."
        ),
    },
    {
        "title": "Junior Data Scientist",
        "company": "Local Startup Co.",
        "location": "Chicago, IL",
        "url": "https://startupco.com/careers/ds-junior",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Exciting startup looking for a junior data scientist. "
            "Basic Python and pandas experience. No specific ML framework required. "
            "Willing to train the right candidate. No prior experience necessary. "
            "Work with Excel and basic SQL. Fun team environment."
        ),
    },
    {
        "title": "Data Scientist - Fraud Detection",
        "company": "JPMorgan Chase",
        "location": "New York, NY",
        "url": "https://jpmorgan.com/careers/example-fraud-007",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "JPMorgan Chase seeks a Data Scientist for the Fraud Detection team. "
            "Build classification and anomaly detection models using Python, scikit-learn, XGBoost. "
            "Work with large-scale transaction data in Spark and Hive. "
            "Strong SQL skills and experience with PostgreSQL required. "
            "Risk analytics background preferred. "
            "Sponsorship not available; must have existing work authorization."
        ),
    },
    {
        "title": "ML Engineer - Recommendation Systems",
        "company": "Spotify",
        "location": "New York, NY (Remote-friendly)",
        "url": "https://www.lifeatspotify.com/jobs/example-rec-008",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Spotify is growing its ML team! We need an engineer to build "
            "recommendation systems using collaborative filtering, matrix factorization, "
            "and deep learning. Python, TensorFlow, Spark, Kafka required. "
            "Experience with A/B testing frameworks and feature engineering. "
            "We sponsor H1B visas and support OPT/CPT candidates. "
            "MLflow or Kubeflow experience is a strong plus."
        ),
    },
    {
        "title": "Research Scientist - Computer Vision",
        "company": "Apple",
        "location": "Cupertino, CA",
        "url": "https://jobs.apple.com/en-us/details/example-cv-009",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Apple Vision Pro team is looking for a Research Scientist specializing "
            "in computer vision and deep learning. PyTorch, CNNs, object detection. "
            "Published research preferred. Strong Python and C++ skills. "
            "Experience deploying models to edge devices. "
            "PhD in Computer Science or Electrical Engineering. "
            "We provide visa sponsorship for highly qualified candidates."
        ),
    },
    {
        "title": "Senior Analytics Engineer",
        "company": "Databricks",
        "location": "San Francisco, CA",
        "url": "https://www.databricks.com/company/careers/example-ae-010",
        "source": "Demo",
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            "Databricks seeks a Senior Analytics Engineer to build robust data pipelines. "
            "dbt, Spark, Python, SQL are core tools. Experience with Snowflake and "
            "BigQuery highly valued. Strong data modelling skills. "
            "Collaborate with data scientists and stakeholders. "
            "5+ years experience. Competitive salary and equity. "
            "We are open to sponsoring H1B visas for the right candidate."
        ),
    },
]


def generate_demo_jobs() -> list[dict]:
    """Return the curated demo job dataset with slight timestamp variation."""
    jobs = []
    for i, job in enumerate(_DEMO_JOBS):
        # Vary posted time slightly so jobs look freshly scraped
        posted = (datetime.now() - timedelta(hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M")
        jobs.append({**job, "posted_date": posted})
    logger.info("Demo mode: generated %d sample jobs.", len(jobs))
    return jobs


# ---------------------------------------------------------------------------
# Real scraper helpers (production mode)
# ---------------------------------------------------------------------------

def _scrape_indeed(query: str, location: str, max_results: int) -> list[dict]:
    """
    Scrape Indeed job listings for a given query and location.

    NOTE: Indeed's anti-bot measures mean this may return empty or blocked
    results in production. For reliable data, consider:
      - Indeed Publisher API (requires approval)
      - A Selenium-based browser automation approach
      - Third-party scraping APIs (ScraperAPI, BrightData)

    This implementation makes a best-effort request and parses the HTML.
    """
    jobs: list[dict] = []
    base_url = "https://www.indeed.com/jobs"
    params = {
        "q": query,
        "l": location,
        "fromage": 1,        # last 24 hours
        "sort": "date",
        "limit": min(max_results, 50),
    }

    try:
        resp = requests.get(
            base_url,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Indeed's structure: job cards have data-jk attribute
        cards = soup.find_all("div", attrs={"data-jk": True})
        logger.debug("Indeed returned %d job cards for '%s' in '%s'.", len(cards), query, location)

        for card in cards[:max_results]:
            try:
                title_el  = card.find("h2", class_=lambda c: c and "jobTitle" in c)
                comp_el   = card.find("span", attrs={"data-testid": "company-name"})
                loc_el    = card.find("div", attrs={"data-testid": "text-location"})
                desc_el   = card.find("div", class_=lambda c: c and "job-snippet" in c)
                jk        = card.get("data-jk", "")
                job_url   = f"https://www.indeed.com/viewjob?jk={jk}" if jk else ""

                jobs.append({
                    "title":       title_el.get_text(strip=True) if title_el else "Unknown",
                    "company":     comp_el.get_text(strip=True) if comp_el else "Unknown",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         job_url,
                    "source":      "Indeed",
                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                })
            except Exception as exc:
                logger.debug("Error parsing Indeed card: %s", exc)

        time.sleep(SCRAPE_DELAY_SECONDS)

    except requests.exceptions.RequestException as exc:
        logger.warning("Indeed scraping failed for '%s': %s", query, exc)

    return jobs


def _scrape_linkedin(query: str, location: str, max_results: int) -> list[dict]:
    """
    Scrape LinkedIn public job search results.

    NOTE: LinkedIn aggressively blocks automated access. This parser targets
    the public /jobs/search endpoint which returns structured HTML for
    non-authenticated sessions. Authentication-required job details need
    Selenium with a logged-in session, or the LinkedIn Jobs API.

    In production: integrate Selenium with a real browser profile here.
    """
    jobs: list[dict] = []
    base_url = "https://www.linkedin.com/jobs/search"
    params = {
        "keywords": query,
        "location": location,
        "f_TPR": "r86400",    # Posted in last 24 hours (86400 seconds)
        "sortBy": "DD",
        "start": 0,
    }

    try:
        resp = requests.get(
            base_url,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_=lambda c: c and "base-card" in (c or ""))
        logger.debug("LinkedIn returned %d cards for '%s'.", len(cards), query)

        for card in cards[:max_results]:
            try:
                title_el = card.find("h3", class_=lambda c: c and "base-search-card__title" in (c or ""))
                comp_el  = card.find("h4", class_=lambda c: c and "base-search-card__subtitle" in (c or ""))
                loc_el   = card.find("span", class_=lambda c: c and "job-search-card__location" in (c or ""))
                link_el  = card.find("a", class_=lambda c: c and "base-card__full-link" in (c or ""))

                jobs.append({
                    "title":       title_el.get_text(strip=True) if title_el else "Unknown",
                    "company":     comp_el.get_text(strip=True) if comp_el else "Unknown",
                    "location":    loc_el.get_text(strip=True) if loc_el else location,
                    "url":         link_el["href"] if link_el else "",
                    "source":      "LinkedIn",
                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    # LinkedIn doesn't include full description in list view;
                    # a second request per job would be needed for full text.
                    # For demo purposes we use a placeholder.
                    "description": (
                        f"{title_el.get_text(strip=True) if title_el else ''} "
                        f"at {comp_el.get_text(strip=True) if comp_el else ''} "
                        f"in {loc_el.get_text(strip=True) if loc_el else location}. "
                        "Python, SQL, machine learning, data science position."
                    ),
                })
            except Exception as exc:
                logger.debug("Error parsing LinkedIn card: %s", exc)

        time.sleep(SCRAPE_DELAY_SECONDS)

    except requests.exceptions.RequestException as exc:
        logger.warning("LinkedIn scraping failed for '%s': %s", query, exc)

    return jobs


def scrape_jobs(
    queries: Optional[list[str]] = None,
    locations: Optional[list[str]] = None,
    max_per_source: int = MAX_JOBS_PER_SOURCE,
) -> list[dict]:
    """
    Scrape jobs from configured sources.

    In DEMO_MODE (env DEMO_MODE=true) returns pre-built sample data.
    In production mode queries Indeed and LinkedIn.

    Args:
        queries:        List of search queries (defaults to config list).
        locations:      List of locations to search (defaults to config list).
        max_per_source: Maximum jobs to collect per source per query.

    Returns:
        Deduplicated list of raw job dicts.
    """
    if DEMO_MODE:
        return generate_demo_jobs()

    queries   = queries or JOB_SEARCH_QUERIES
    locations = locations or JOB_LOCATIONS
    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        for location in locations:
            logger.info("Scraping Indeed: query='%s', location='%s'", query, location)
            indeed_jobs = _scrape_indeed(query, location, max_per_source)
            for job in indeed_jobs:
                if job.get("url") not in seen_urls:
                    all_jobs.append(job)
                    seen_urls.add(job.get("url", ""))

            logger.info("Scraping LinkedIn: query='%s', location='%s'", query, location)
            linkedin_jobs = _scrape_linkedin(query, location, max_per_source)
            for job in linkedin_jobs:
                if job.get("url") not in seen_urls:
                    all_jobs.append(job)
                    seen_urls.add(job.get("url", ""))

    logger.info("Total unique jobs scraped: %d", len(all_jobs))
    return all_jobs


# ---------------------------------------------------------------------------
# CSV backup
# ---------------------------------------------------------------------------

def save_jobs_csv(jobs: list[dict], csv_path: Path = JOBS_LOG_CSV) -> None:
    """
    Append classified jobs to the local CSV backup.

    Creates the file with a header row if it doesn't exist.

    Args:
        jobs:     Classified job dicts.
        csv_path: Output CSV path.
    """
    csv_path = Path(csv_path)
    fieldnames = [
        "date", "title", "company", "match_pct",
        "h1b_sponsor", "is_maang", "is_fortune500",
        "portal", "location", "source", "url",
        "key_skills", "ats_keywords", "posted_date",
    ]

    file_exists = csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()

        for job in jobs:
            writer.writerow({
                "date":         datetime.now().strftime("%Y-%m-%d %H:%M"),
                "title":        job.get("title", ""),
                "company":      job.get("company", ""),
                "match_pct":    job.get("match_pct", 0),
                "h1b_sponsor":  job.get("h1b_sponsor"),
                "is_maang":     job.get("is_maang", False),
                "is_fortune500":job.get("is_fortune500", False),
                "portal":       job.get("portal", "Unknown"),
                "location":     job.get("location", ""),
                "source":       job.get("source", ""),
                "url":          job.get("url", ""),
                "key_skills":   "; ".join(job.get("key_skills", [])),
                "ats_keywords": "; ".join(job.get("ats_keywords", [])),
                "posted_date":  job.get("posted_date", ""),
            })

    logger.info("CSV backup: %d jobs appended to '%s'.", len(jobs), csv_path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    """
    Execute the complete job-finding pipeline.

    Steps:
      1. Load resume
      2. Scrape jobs
      3. Classify and filter jobs (>= MATCH_THRESHOLD_PCT%)
      4. Log to Google Sheets
      5. Save CSV backup
      6. Send email notification
      7. Write execution log

    Returns:
        Run summary dict.
    """
    pipeline_start = time.time()
    errors: list[str] = []

    logger.info("=" * 60)
    logger.info("Job Finder pipeline starting – %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Demo mode: %s", DEMO_MODE)

    # ----- Step 1: Load resume -----
    logger.info("[1/7] Loading resume from '%s'...", RESUME_PDF_PATH)
    try:
        resume_profile = load_resume(RESUME_PDF_PATH)
        logger.info(
            "Resume loaded: %d technical skills, %d soft skills.",
            len(resume_profile["technical_skills"]),
            len(resume_profile["soft_skills"]),
        )
    except Exception as exc:
        err_msg = f"Resume loading failed: {exc}"
        logger.error(err_msg, exc_info=True)
        errors.append(err_msg)
        return {"error": err_msg, "above_threshold": 0}

    # ----- Step 2: Scrape jobs -----
    logger.info("[2/7] Scraping jobs...")
    try:
        raw_jobs = scrape_jobs()
    except Exception as exc:
        err_msg = f"Job scraping failed: {exc}"
        logger.error(err_msg, exc_info=True)
        errors.append(err_msg)
        raw_jobs = []

    logger.info("Scraped %d raw jobs.", len(raw_jobs))

    # ----- Step 3: Classify and filter -----
    logger.info("[3/7] Classifying jobs (threshold: %d%%)...", MATCH_THRESHOLD_PCT)
    try:
        qualified_jobs = classify_jobs_batch(raw_jobs, resume_profile)
    except Exception as exc:
        err_msg = f"Job classification failed: {exc}"
        logger.error(err_msg, exc_info=True)
        errors.append(err_msg)
        qualified_jobs = []

    logger.info(
        "%d of %d jobs met the %d%% match threshold.",
        len(qualified_jobs), len(raw_jobs), MATCH_THRESHOLD_PCT,
    )

    if qualified_jobs:
        logger.info("Top matches:")
        for job in qualified_jobs[:5]:
            logger.info(
                "  %.1f%%  %s @ %s  |  H1B=%s  MAANG=%s  F500=%s",
                job["match_pct"], job["title"], job["company"],
                job.get("h1b_sponsor"), job.get("is_maang"), job.get("is_fortune500"),
            )

    # ----- Step 4: Google Sheets -----
    logged_count = 0
    if qualified_jobs and SHEETS_AVAILABLE:
        logger.info("[4/7] Logging to Google Sheets...")
        try:
            logged_count = log_jobs_to_sheet(qualified_jobs)
        except FileNotFoundError as exc:
            # Credentials missing – non-fatal
            err_msg = f"Google Sheets skipped (credentials missing): {exc}"
            logger.warning(err_msg)
            errors.append(err_msg)
        except Exception as exc:
            err_msg = f"Google Sheets logging failed: {exc}"
            logger.error(err_msg, exc_info=True)
            errors.append(err_msg)
    else:
        logger.info("[4/7] Google Sheets logging skipped (no qualified jobs or unavailable).")

    # ----- Step 5: CSV backup -----
    logger.info("[5/7] Saving CSV backup...")
    if qualified_jobs:
        try:
            save_jobs_csv(qualified_jobs)
        except Exception as exc:
            err_msg = f"CSV backup failed: {exc}"
            logger.error(err_msg, exc_info=True)
            errors.append(err_msg)
    else:
        logger.info("No qualified jobs to save to CSV.")

    # ----- Step 6: Email notification -----
    logger.info("[6/7] Sending email notification...")
    email_sent = False
    run_meta = {
        "run_time":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources":       "Demo" if DEMO_MODE else "Indeed, LinkedIn",
        "total_scraped": len(raw_jobs),
    }
    try:
        email_sent = notify_high_match_jobs(qualified_jobs, run_meta=run_meta)
    except Exception as exc:
        err_msg = f"Email notification failed: {exc}"
        logger.error(err_msg, exc_info=True)
        errors.append(err_msg)

    # ----- Step 7: Execution log -----
    logger.info("[7/7] Writing execution log...")
    duration = time.time() - pipeline_start
    sources = ["Demo"] if DEMO_MODE else ["Indeed", "LinkedIn"]

    summary = build_run_summary(
        all_jobs=raw_jobs,
        qualified_jobs=qualified_jobs,
        logged_count=logged_count,
        email_sent=email_sent,
        sources=sources,
        duration_seconds=duration,
        errors=errors,
    )

    try:
        log_execution(summary)
    except Exception as exc:
        logger.error("Execution log write failed: %s", exc, exc_info=True)

    logger.info(
        "Pipeline complete in %.1fs  |  %d qualified jobs  |  %d logged to Sheets.",
        duration, len(qualified_jobs), logged_count,
    )
    logger.info("=" * 60)

    return summary


# Alias used by scheduler.py
run_once = run_pipeline


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    result = run_pipeline()

    # Print a compact summary (omit nested job dicts for readability)
    printable = {k: v for k, v in result.items() if k != "top_jobs"}
    print("\n--- Run Summary ---")
    print(json.dumps(printable, indent=2))

    if result.get("top_jobs"):
        print(f"\nTop {min(5, len(result['top_jobs']))} matched jobs:")
        for job in result["top_jobs"][:5]:
            print(
                f"  {job['match_pct']:.1f}%  |  {job['title']}  @  {job['company']}  |  "
                f"H1B={job.get('h1b_sponsor')}  MAANG={job.get('is_maang')}  "
                f"F500={job.get('is_fortune500')}"
            )
