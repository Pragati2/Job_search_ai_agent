"""
notifier.py - Notification and execution logging subsystem.

Provides:
  notify_high_match_jobs(jobs)      - Email alert for qualifying jobs
  log_execution(summary)            - Append run record to execution_log.txt
  build_run_summary(jobs, meta)     - Compile a human-readable summary report
"""

import logging
import os
import smtplib
import textwrap
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    NOTIFY_TO,
    MATCH_THRESHOLD_PCT,
    EXECUTION_LOG,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def _build_html_body(jobs: list[dict], run_meta: dict) -> str:
    """
    Render an HTML email body with a summary table of matched jobs.
    """
    rows_html = ""
    for job in jobs:
        h1b_badge = (
            '<span style="color:green;font-weight:bold">YES</span>'
            if job.get("h1b_sponsor") is True
            else '<span style="color:red">NO</span>'
            if job.get("h1b_sponsor") is False
            else '<span style="color:grey">Unknown</span>'
        )
        maang_badge = (
            '<span style="color:green;font-weight:bold">YES</span>'
            if job.get("is_maang")
            else "No"
        )
        f500_badge = (
            '<span style="color:green;font-weight:bold">YES</span>'
            if job.get("is_fortune500")
            else "No"
        )
        url = job.get("url", "#")
        rows_html += f"""
        <tr>
          <td><a href="{url}">{job.get('title','')}</a></td>
          <td>{job.get('company','')}</td>
          <td style="text-align:center;font-weight:bold">{job.get('match_pct', 0):.1f}%</td>
          <td style="text-align:center">{h1b_badge}</td>
          <td style="text-align:center">{maang_badge}</td>
          <td style="text-align:center">{f500_badge}</td>
          <td>{job.get('portal','Unknown')}</td>
          <td>{job.get('location','')}</td>
        </tr>"""

    skills_section = ""
    for job in jobs[:5]:     # Top 5 jobs get a skills breakdown
        kw = ", ".join(job.get("ats_keywords", [])[:8])
        skills_section += f"""
        <p><strong>{job.get('title','')} @ {job.get('company','')}</strong><br>
        ATS Keywords to highlight: <em>{kw}</em></p>"""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
    <h2 style="color:#2c5f8a;">Job Finder Run Report</h2>
    <p>Run time: <strong>{run_meta.get('run_time','')}</strong><br>
       Source(s): {run_meta.get('sources','')}<br>
       Total scraped: {run_meta.get('total_scraped', 0)} &nbsp;|&nbsp;
       Matched (>={MATCH_THRESHOLD_PCT}%): <strong>{len(jobs)}</strong></p>

    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse;width:100%;font-size:13px;">
      <thead style="background:#2c5f8a;color:white;">
        <tr>
          <th>Job Title</th><th>Company</th><th>Match %</th>
          <th>H1B</th><th>MAANG</th><th>F500</th>
          <th>Portal</th><th>Location</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <h3 style="color:#2c5f8a;">ATS Keyword Tips</h3>
    {skills_section}

    <hr>
    <p style="font-size:11px;color:#888;">
      Sent by Job Finder Agent &bull; Threshold: {MATCH_THRESHOLD_PCT}%
    </p>
    </body>
    </html>
    """
    return html


def _build_plain_body(jobs: list[dict], run_meta: dict) -> str:
    """Plain-text fallback body."""
    lines = [
        "JOB FINDER RUN REPORT",
        "=" * 50,
        f"Run time : {run_meta.get('run_time', '')}",
        f"Sources  : {run_meta.get('sources', '')}",
        f"Scraped  : {run_meta.get('total_scraped', 0)}",
        f"Matched  : {len(jobs)} (>= {MATCH_THRESHOLD_PCT}%)",
        "",
        "TOP MATCHES",
        "-" * 50,
    ]
    for job in jobs:
        h1b = (
            "YES" if job.get("h1b_sponsor") is True
            else "NO" if job.get("h1b_sponsor") is False
            else "Unknown"
        )
        lines += [
            f"  {job.get('match_pct', 0):.1f}%  |  {job.get('title','')}  @  {job.get('company','')}",
            f"         Location: {job.get('location','')}",
            f"         H1B: {h1b}  |  MAANG: {job.get('is_maang',False)}  |  F500: {job.get('is_fortune500',False)}",
            f"         URL: {job.get('url','')}",
            "",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API – email notification
# ---------------------------------------------------------------------------

def notify_high_match_jobs(
    jobs: list[dict],
    run_meta: Optional[dict] = None,
    recipients: Optional[list[str]] = None,
) -> bool:
    """
    Send an email notification with details of matched jobs.

    Args:
        jobs:       Classified + filtered job dicts (already above threshold).
        run_meta:   Dict with run context (run_time, sources, total_scraped).
        recipients: Override list of email addresses. Falls back to NOTIFY_TO.

    Returns:
        True if email sent successfully, False otherwise.
    """
    if not jobs:
        logger.info("No qualifying jobs – skipping email notification.")
        return False

    # Determine recipients
    to_addresses: list[str] = []
    if recipients:
        to_addresses = [r.strip() for r in recipients if r.strip()]
    elif NOTIFY_TO:
        to_addresses = [r.strip() for r in NOTIFY_TO.split(",") if r.strip()]

    if not to_addresses:
        logger.warning(
            "NOTIFY_TO is not configured – email notification skipped. "
            "Set NOTIFY_TO in your .env file."
        )
        return False

    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning(
            "SMTP credentials not configured (SMTP_USER / SMTP_PASSWORD). "
            "Email notification skipped."
        )
        return False

    meta = run_meta or {
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": "Various",
        "total_scraped": len(jobs),
    }

    # Build message
    subject = (
        f"[Job Finder] {len(jobs)} match(es) found – "
        f"{datetime.now().strftime('%b %d %Y %H:%M')}"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(to_addresses)

    plain = _build_plain_body(jobs, meta)
    html  = _build_html_body(jobs, meta)

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_addresses, msg.as_string())

        logger.info(
            "Email notification sent to %d recipient(s): %s",
            len(to_addresses), ", ".join(to_addresses),
        )
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD. "
            "For Gmail, use an App Password (not your account password)."
        )
    except smtplib.SMTPConnectError as exc:
        logger.error("Cannot connect to SMTP server %s:%d – %s", SMTP_HOST, SMTP_PORT, exc)
    except Exception as exc:
        logger.error("Unexpected error sending email: %s", exc, exc_info=True)

    return False


# ---------------------------------------------------------------------------
# Execution log
# ---------------------------------------------------------------------------

def log_execution(summary: dict, log_path: Path = EXECUTION_LOG) -> None:
    """
    Append a structured run record to execution_log.txt.

    Args:
        summary:  Dict with run statistics (see build_run_summary).
        log_path: Path to the log file (default from config).
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 70

    lines = [
        separator,
        f"RUN  : {timestamp}",
        f"Source(s)        : {summary.get('sources', 'N/A')}",
        f"Total scraped    : {summary.get('total_scraped', 0)}",
        f"Above threshold  : {summary.get('above_threshold', 0)} (>= {MATCH_THRESHOLD_PCT}%)",
        f"Logged to Sheet  : {summary.get('logged_to_sheet', 0)}",
        f"Email sent       : {summary.get('email_sent', False)}",
        f"Duration (s)     : {summary.get('duration_seconds', 'N/A')}",
        "",
        "Top matches:",
    ]

    for job in summary.get("top_jobs", [])[:5]:
        lines.append(
            f"  {job.get('match_pct', 0):.1f}%  {job.get('title','')}  @  {job.get('company','')}"
        )

    errors = summary.get("errors", [])
    if errors:
        lines += ["", "Errors:"]
        for err in errors:
            lines.append(f"  - {err}")

    lines.append("")

    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    logger.info("Execution record appended to '%s'.", log_path)


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_run_summary(
    all_jobs: list[dict],
    qualified_jobs: list[dict],
    logged_count: int,
    email_sent: bool,
    sources: list[str],
    duration_seconds: float,
    errors: Optional[list[str]] = None,
) -> dict:
    """
    Compile a run summary dict consumed by log_execution() and the orchestrator.

    Args:
        all_jobs:         All jobs scraped (before threshold filter).
        qualified_jobs:   Jobs that met the match threshold.
        logged_count:     Rows actually written to Google Sheets.
        email_sent:       Whether the notification email was sent.
        sources:          List of scraping sources used.
        duration_seconds: Wall-clock runtime in seconds.
        errors:           List of error messages encountered.

    Returns:
        Summary dict.
    """
    return {
        "run_time":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources":         ", ".join(sources),
        "total_scraped":   len(all_jobs),
        "above_threshold": len(qualified_jobs),
        "logged_to_sheet": logged_count,
        "email_sent":      email_sent,
        "duration_seconds": round(duration_seconds, 2),
        "top_jobs":        qualified_jobs[:10],
        "errors":          errors or [],
    }


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Test execution log
    sample_summary = build_run_summary(
        all_jobs=[{"title": "Data Scientist", "company": "Acme", "match_pct": 85.0}],
        qualified_jobs=[{"title": "Data Scientist", "company": "Acme",
                         "match_pct": 85.0, "is_maang": False, "is_fortune500": False,
                         "h1b_sponsor": None, "location": "Remote",
                         "url": "https://example.com"}],
        logged_count=1,
        email_sent=False,
        sources=["Demo"],
        duration_seconds=3.14,
    )
    log_execution(sample_summary)
    print("Execution log updated.")
    print(json.dumps({k: v for k, v in sample_summary.items() if k != "top_jobs"}, indent=2))
