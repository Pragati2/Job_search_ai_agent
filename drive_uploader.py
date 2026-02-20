"""
drive_uploader.py - Google Sheets integration for job logging.

Provides:
  SheetsLogger            - Main class handling auth, write, formatting
  log_jobs_to_sheet(jobs) - Convenience function for the orchestrator

Authentication:
  Reads a service-account credentials JSON whose path is set via:
    GOOGLE_CREDENTIALS_PATH env var  (default: credentials.json next to this file)

The spreadsheet is identified by SPREADSHEET_ID in .env.
If SPREADSHEET_ID is empty, a new spreadsheet is created automatically.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    SHEET_COLUMNS,
    SHEET_NAME,
    GOOGLE_SHEETS_SCOPES,
    COL_H1B, COL_MAANG, COL_F500, COL_MATCH,
    COLOR_GREEN, COLOR_RED, COLOR_YELLOW, COLOR_TEAL,
    CREDENTIALS_JSON,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_letter(col_index: int) -> str:
    """Convert 1-based column index to spreadsheet letter (A, B, …, Z, AA…)."""
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _bool_to_str(value: Optional[bool]) -> str:
    """Render a tri-state bool as a human-readable string."""
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    return "Unknown"


def _row_for_job(job: dict) -> list:
    """
    Convert a classified job dict into a row matching SHEET_COLUMNS order.

    SHEET_COLUMNS = [
      "Date", "Job Title", "Company", "Match %", "H1B Sponsor",
      "MAANG", "Fortune 500", "Job URL", "Application Portal",
      "Key Skills Matched", "ATS Keywords", "Location", "Source", "Posted Date"
    ]
    """
    return [
        datetime.now().strftime("%Y-%m-%d %H:%M"),          # Date
        job.get("title", ""),                                # Job Title
        job.get("company", ""),                              # Company
        job.get("match_pct", 0.0),                          # Match %
        _bool_to_str(job.get("h1b_sponsor")),               # H1B Sponsor
        str(job.get("is_maang", False)).upper(),             # MAANG
        str(job.get("is_fortune500", False)).upper(),        # Fortune 500
        job.get("url", ""),                                  # Job URL
        job.get("portal", "Unknown"),                        # Application Portal
        ", ".join(job.get("key_skills", [])[:10]),           # Key Skills Matched
        ", ".join(job.get("ats_keywords", [])[:10]),         # ATS Keywords
        job.get("location", ""),                             # Location
        job.get("source", ""),                               # Source
        job.get("posted_date", ""),                          # Posted Date
    ]


def _make_color_rule(
    sheet_id: int,
    col_index: int,          # 1-based
    match_value: str,        # cell value to match (e.g. "TRUE")
    bg_color: dict,
) -> dict:
    """Build a Sheets API conditional formatting request for an exact-text match."""
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,          # skip header row
                    "startColumnIndex": col_index - 1,
                    "endColumnIndex": col_index,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": match_value}],
                    },
                    "format": {"backgroundColor": bg_color},
                },
            },
            "index": 0,
        }
    }


def _make_gradient_rule(
    sheet_id: int,
    col_index: int,
) -> dict:
    """Build a gradient conditional format for the Match % column."""
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": col_index - 1,
                    "endColumnIndex": col_index,
                }],
                "gradientRule": {
                    "minpoint": {
                        "color": COLOR_RED,
                        "type": "NUMBER",
                        "value": "0",
                    },
                    "midpoint": {
                        "color": COLOR_YELLOW,
                        "type": "NUMBER",
                        "value": "72",
                    },
                    "maxpoint": {
                        "color": COLOR_TEAL,
                        "type": "NUMBER",
                        "value": "100",
                    },
                },
            },
            "index": 0,
        }
    }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SheetsLogger:
    """
    Manages writing job data to a Google Sheet with conditional formatting
    and duplicate detection.
    """

    def __init__(self, spreadsheet_id: str = "", credentials_path: Optional[Path] = None):
        """
        Args:
            spreadsheet_id:   ID of the target spreadsheet (from URL).
                              Pass "" to auto-create.
            credentials_path: Path to service account JSON file.
                              Defaults to CREDENTIALS_JSON from config.
        """
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID", "")
        creds_path = credentials_path or Path(
            os.getenv("GOOGLE_CREDENTIALS_PATH", str(CREDENTIALS_JSON))
        )

        self._service = self._build_service(creds_path)
        self._sheet_id: Optional[int] = None   # numeric GID of the worksheet

        if not self.spreadsheet_id:
            self.spreadsheet_id = self._create_spreadsheet()
        else:
            self._ensure_sheet_exists()

        # Cache existing rows for duplicate detection (company+title compound key)
        self._existing_keys: set[str] = self._load_existing_keys()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _build_service(self, creds_path: Path):
        """Authenticate with a service account and return the Sheets service."""
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Google credentials file not found: {creds_path}\n"
                "Set GOOGLE_CREDENTIALS_PATH in your .env file."
            )

        creds = service_account.Credentials.from_service_account_file(
            str(creds_path),
            scopes=GOOGLE_SHEETS_SCOPES,
        )
        service = build("sheets", "v4", credentials=creds)
        logger.info("Google Sheets service authenticated successfully.")
        return service

    # ------------------------------------------------------------------
    # Spreadsheet / sheet management
    # ------------------------------------------------------------------

    def _create_spreadsheet(self) -> str:
        """Create a new spreadsheet and return its ID."""
        body = {
            "properties": {"title": SHEET_NAME},
            "sheets": [{"properties": {"title": SHEET_NAME}}],
        }
        result = (
            self._service.spreadsheets()
            .create(body=body, fields="spreadsheetId")
            .execute()
        )
        sid = result["spreadsheetId"]
        logger.info("Created new spreadsheet: %s", sid)
        self._write_header(sid)
        return sid

    def _ensure_sheet_exists(self) -> None:
        """Verify the target spreadsheet is accessible and get its sheet GID."""
        try:
            meta = (
                self._service.spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id)
                .execute()
            )
            sheets = meta.get("sheets", [])
            if not sheets:
                raise ValueError("Spreadsheet has no sheets.")

            # Use the first sheet (or find one named SHEET_NAME)
            target = next(
                (s for s in sheets if s["properties"]["title"] == SHEET_NAME),
                sheets[0],
            )
            self._sheet_id = target["properties"]["sheetId"]

            # Check if header row exists; write it if not
            result = (
                self._service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{SHEET_NAME}!A1:A1",
                )
                .execute()
            )
            if not result.get("values"):
                self._write_header(self.spreadsheet_id)

        except HttpError as exc:
            raise ConnectionError(
                f"Cannot access spreadsheet '{self.spreadsheet_id}': {exc}"
            ) from exc

    def _write_header(self, spreadsheet_id: str) -> None:
        """Write the column header row to row 1."""
        body = {"values": [SHEET_COLUMNS]}
        self._service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body=body,
        ).execute()

        # Bold + freeze header row
        if self._sheet_id is not None:
            self._apply_header_formatting(spreadsheet_id)

        logger.info("Header row written to sheet.")

    def _apply_header_formatting(self, spreadsheet_id: str) -> None:
        """Bold the header row and freeze it."""
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": self._sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": self._sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def _load_existing_keys(self) -> set[str]:
        """
        Read existing rows from the sheet and build compound keys
        (lowercased 'Company|Job Title') to detect duplicates.
        """
        try:
            result = (
                self._service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{SHEET_NAME}!B2:C",   # Job Title (B) and Company (C)
                )
                .execute()
            )
            rows = result.get("values", [])
            # rows are [title, company] but columns are B=title, C=company
            return {
                f"{row[1].lower()}|{row[0].lower()}"
                for row in rows
                if len(row) >= 2
            }
        except HttpError:
            return set()

    def _is_duplicate(self, job: dict) -> bool:
        """Return True if this company+title pair already exists in the sheet."""
        key = f"{job.get('company', '').lower()}|{job.get('title', '').lower()}"
        return key in self._existing_keys

    def _register_key(self, job: dict) -> None:
        key = f"{job.get('company', '').lower()}|{job.get('title', '').lower()}"
        self._existing_keys.add(key)

    # ------------------------------------------------------------------
    # Writing data
    # ------------------------------------------------------------------

    def log_jobs(self, jobs: list[dict]) -> int:
        """
        Append qualified job rows to the Google Sheet.

        Args:
            jobs: List of classified job dicts (output of brain.classify_job).

        Returns:
            Number of rows actually written (skips duplicates).
        """
        rows_to_write: list[list] = []
        skipped = 0

        for job in jobs:
            if self._is_duplicate(job):
                logger.debug(
                    "Duplicate skipped: '%s' @ %s",
                    job.get("title"), job.get("company"),
                )
                skipped += 1
                continue
            rows_to_write.append(_row_for_job(job))
            self._register_key(job)

        if not rows_to_write:
            logger.info("No new jobs to log (%d duplicates skipped).", skipped)
            return 0

        body = {"values": rows_to_write}
        self._service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",   # allows numbers to be numbers
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()

        logger.info(
            "Logged %d new jobs to Google Sheet (%d duplicates skipped).",
            len(rows_to_write), skipped,
        )

        # Apply conditional formatting after writing (idempotent-ish)
        self._apply_conditional_formatting()
        return len(rows_to_write)

    # ------------------------------------------------------------------
    # Conditional formatting
    # ------------------------------------------------------------------

    def _apply_conditional_formatting(self) -> None:
        """
        Apply colour rules:
          - H1B Sponsor col:   TRUE -> green, FALSE -> red
          - MAANG col:         TRUE -> green, FALSE -> red
          - Fortune 500 col:   TRUE -> green, FALSE -> red
          - Match % col:       gradient red(0) -> yellow(72) -> teal(100)
        """
        if self._sheet_id is None:
            return

        requests = [
            # H1B
            _make_color_rule(self._sheet_id, COL_H1B, "TRUE",  COLOR_GREEN),
            _make_color_rule(self._sheet_id, COL_H1B, "FALSE", COLOR_RED),
            # MAANG
            _make_color_rule(self._sheet_id, COL_MAANG, "TRUE",  COLOR_GREEN),
            _make_color_rule(self._sheet_id, COL_MAANG, "FALSE", COLOR_RED),
            # Fortune 500
            _make_color_rule(self._sheet_id, COL_F500, "TRUE",  COLOR_GREEN),
            _make_color_rule(self._sheet_id, COL_F500, "FALSE", COLOR_RED),
            # Match % gradient
            _make_gradient_rule(self._sheet_id, COL_MATCH),
        ]

        try:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()
            logger.debug("Conditional formatting applied.")
        except HttpError as exc:
            # Non-fatal – formatting is cosmetic
            logger.warning("Could not apply conditional formatting: %s", exc)


# ---------------------------------------------------------------------------
# Convenience function for the orchestrator
# ---------------------------------------------------------------------------

def log_jobs_to_sheet(
    jobs: list[dict],
    spreadsheet_id: str = "",
    credentials_path: Optional[Path] = None,
) -> int:
    """
    Instantiate SheetsLogger and log jobs in one call.

    Args:
        jobs:             Classified job dicts.
        spreadsheet_id:   Target sheet ID (reads from env if blank).
        credentials_path: Path to service-account JSON.

    Returns:
        Number of rows written.
    """
    logger_obj = SheetsLogger(
        spreadsheet_id=spreadsheet_id,
        credentials_path=credentials_path,
    )
    return logger_obj.log_jobs(jobs)
