"""
Data_Extraction.py - Resume PDF extraction and initial keyword harvesting.

Provides:
  get_resume_text(file_path)  -> raw text string from PDF
  extract_resume_keywords(text) -> dict with categorised keyword lists
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

# Import keyword reference lists from config
try:
    from config import TECH_SKILLS_SET, SOFT_SKILLS_SET
except ImportError:
    # Fallback minimal sets if config is not yet on PYTHONPATH
    TECH_SKILLS_SET = {
        "python", "sql", "r", "machine learning", "deep learning",
        "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn",
        "statistics", "data science", "nlp", "aws", "spark",
    }
    SOFT_SKILLS_SET = {
        "communication", "collaboration", "leadership",
        "problem solving", "analytical", "teamwork",
    }

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def get_resume_text(file_path: str | Path) -> str:
    """
    Extract all text from a PDF resume.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        A single string containing the concatenated text of all pages.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF yields no extractable text.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {file_path}")

    reader = PdfReader(str(file_path))
    pages_text: list[str] = []

    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        pages_text.append(page_text)
        logger.debug("Page %d extracted %d characters.", i + 1, len(page_text))

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise ValueError(
            f"No text could be extracted from '{file_path}'. "
            "The PDF may be image-only – consider running OCR first."
        )

    logger.info(
        "Extracted %d characters from '%s' (%d page(s)).",
        len(full_text), file_path.name, len(reader.pages),
    )
    return full_text


# ---------------------------------------------------------------------------
# Keyword / skill extraction
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace for reliable matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _extract_section(text: str, heading: str) -> str:
    """
    Heuristically pull text between a section heading and the next heading.
    Returns empty string if the heading is not found.
    """
    # Common heading patterns: "SKILLS", "Skills:", "TECHNICAL SKILLS", etc.
    pattern = re.compile(
        rf"(?i)\b{re.escape(heading)}\b[:\s]*\n(.*?)(?=\n[A-Z][A-Z &]+\n|\Z)",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_resume_keywords(text: str) -> dict:
    """
    Derive a structured keyword profile from raw resume text.

    Args:
        text: Raw text from get_resume_text().

    Returns:
        dict with keys:
          - "technical_skills"  : list[str]  matched technical skills
          - "soft_skills"       : list[str]  matched soft skills
          - "all_keywords"      : list[str]  combined de-duplicated list
          - "job_titles"        : list[str]  detected role titles
          - "education"         : list[str]  detected degrees / institutions
          - "years_experience"  : Optional[int] inferred YOE
          - "raw_text"          : str        the original text (pass-through)
    """
    norm_text = _normalise(text)

    # --- Technical skills ---
    tech_found: list[str] = []
    for skill in sorted(TECH_SKILLS_SET):
        # Use word-boundary matching for short tokens to avoid false positives
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, norm_text):
            tech_found.append(skill)

    # --- Soft skills ---
    soft_found: list[str] = []
    for skill in sorted(SOFT_SKILLS_SET):
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, norm_text):
            soft_found.append(skill)

    # --- Job titles (heuristic) ---
    title_patterns = [
        r"data scientist", r"data analyst", r"machine learning engineer",
        r"ml engineer", r"ai engineer", r"data engineer",
        r"research scientist", r"applied scientist",
        r"business intelligence", r"analytics engineer",
        r"quantitative analyst", r"statistician",
        r"software engineer", r"software developer",
    ]
    titles_found: list[str] = []
    for tp in title_patterns:
        if re.search(tp, norm_text):
            titles_found.append(tp.replace(r"\ ", " "))

    # --- Education (degrees) ---
    edu_patterns = [
        r"bachelor(?:'s)?(?:\s+of)?\s+(?:science|arts|engineering|technology)?",
        r"master(?:'s)?(?:\s+of)?\s+(?:science|arts|engineering|technology)?",
        r"ph\.?d\.?",
        r"b\.?s\.?c?\.?",
        r"m\.?s\.?c?\.?",
        r"mba",
    ]
    edu_found: list[str] = []
    for ep in edu_patterns:
        m = re.search(ep, norm_text)
        if m:
            edu_found.append(m.group(0).strip())

    # --- Years of experience (heuristic: look for "N years" near "experience") ---
    yoe = None  # type: Optional[int]
    yoe_match = re.search(
        r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
        norm_text,
    )
    if yoe_match:
        yoe = int(yoe_match.group(1))

    # --- Combined de-duplicated keyword list ---
    all_kw = list(dict.fromkeys(tech_found + soft_found))

    result = {
        "technical_skills": tech_found,
        "soft_skills": soft_found,
        "all_keywords": all_kw,
        "job_titles": list(dict.fromkeys(titles_found)),
        "education": list(dict.fromkeys(edu_found)),
        "years_experience": yoe,
        "raw_text": text,
    }

    logger.info(
        "Keyword extraction complete: %d technical, %d soft skills found.",
        len(tech_found), len(soft_found),
    )
    return result


# ---------------------------------------------------------------------------
# Convenience one-shot loader
# ---------------------------------------------------------------------------

def load_resume(file_path: str | Path) -> dict:
    """
    Full pipeline: extract PDF text then extract keywords.

    Returns the same dict as extract_resume_keywords() – raw_text included.
    """
    text = get_resume_text(file_path)
    return extract_resume_keywords(text)


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "Pragati_Khekale_DS_GL.pdf"
    profile = load_resume(pdf_path)

    # Print a summary (omit raw_text for readability)
    summary = {k: v for k, v in profile.items() if k != "raw_text"}
    print(json.dumps(summary, indent=2))
