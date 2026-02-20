"""
brain.py - Core NLP, matching, and classification engine.

Provides:
  calculate_match_score(resume_profile, job_text) -> float  (0.0 – 1.0)
  classify_job(job: dict) -> dict                           enriched job dict
  detect_h1b(text) -> bool | None
  detect_maang(company_name, job_text) -> bool
  detect_fortune500(company_name) -> bool
  detect_portal(job_url, job_text) -> str
  extract_ats_keywords(job_text, resume_profile) -> list[str]
"""

from __future__ import annotations

import re
import logging
import math
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from config import (
    TECH_SKILLS_SET,
    SOFT_SKILLS_SET,
    MAANG_ALIASES,
    MAANG_COMPANIES,
    FORTUNE_500_SET,
    H1B_POSITIVE_KEYWORDS,
    H1B_NEGATIVE_KEYWORDS,
    PORTAL_PATTERNS,
    MATCH_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, remove special characters and collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s\.\+\#]", " ", text)   # keep . + # for C#, C++
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenise(text: str) -> list[str]:
    """Split normalised text into word tokens."""
    return _normalise(text).split()


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity (pure Python, no sklearn dependency required)
# ---------------------------------------------------------------------------

def _build_tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Build a TF-IDF weighted frequency dict for a token list."""
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {term: (count / total) * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0

    dot = sum(vec_a[t] * vec_b[t] for t in common)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _compute_idf(corpus: list[list[str]]) -> dict[str, float]:
    """
    Compute IDF weights from a small corpus of token lists.
    IDF(t) = log((N + 1) / (df(t) + 1)) + 1  [smoothed]
    """
    n = len(corpus)
    df: dict[str, int] = {}
    for tokens in corpus:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    return {
        term: math.log((n + 1) / (count + 1)) + 1
        for term, count in df.items()
    }


# ---------------------------------------------------------------------------
# Match score calculation
# ---------------------------------------------------------------------------

def calculate_match_score(
    resume_profile: dict,
    job_text: str,
    alpha: float = 0.65,   # weight for TF-IDF cosine similarity
    beta: float = 0.35,    # weight for direct skill keyword overlap
) -> float:
    """
    Compute a match score between the resume profile and a job posting.

    Combines two signals:
      1. TF-IDF cosine similarity of resume raw text vs job text
      2. Skill keyword overlap ratio (resume skills found in job text)

    Args:
        resume_profile: Output of Data_Extraction.extract_resume_keywords()
        job_text:       Raw text of the job posting
        alpha:          Weight for TF-IDF component (0-1)
        beta:           Weight for keyword overlap component (0-1)

    Returns:
        Score in [0.0, 1.0]
    """
    resume_text = resume_profile.get("raw_text", "")
    if not resume_text or not job_text:
        return 0.0

    # --- Component 1: TF-IDF cosine similarity ---
    resume_tokens = _tokenise(resume_text)
    job_tokens    = _tokenise(job_text)

    idf = _compute_idf([resume_tokens, job_tokens])
    vec_resume = _build_tfidf_vector(resume_tokens, idf)
    vec_job    = _build_tfidf_vector(job_tokens, idf)

    tfidf_sim = _cosine_similarity(vec_resume, vec_job)

    # --- Component 2: Skill keyword overlap ---
    resume_skills = set(resume_profile.get("all_keywords", []))
    norm_job = _normalise(job_text)

    matched_skills = 0
    for skill in resume_skills:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, norm_job):
            matched_skills += 1

    # Overlap ratio: how many of the resume's known skills appear in the job
    overlap_ratio = matched_skills / max(len(resume_skills), 1)

    # --- Combine ---
    combined = alpha * tfidf_sim + beta * overlap_ratio

    # Clip to [0, 1]
    score = max(0.0, min(1.0, combined))

    logger.debug(
        "Match score: %.3f  (tfidf=%.3f, overlap=%.3f, matched_skills=%d/%d)",
        score, tfidf_sim, overlap_ratio, matched_skills, len(resume_skills),
    )
    return score


# ---------------------------------------------------------------------------
# H1B sponsorship detection
# ---------------------------------------------------------------------------

def detect_h1b(text: str) -> Optional[bool]:
    """
    Detect whether a job posting mentions H1B sponsorship.

    Returns:
        True   – positive sponsorship signals found
        False  – negative / no-sponsorship signals found
        None   – no sponsorship signals found at all
    """
    norm = _normalise(text)

    positive = any(kw in norm for kw in H1B_POSITIVE_KEYWORDS)
    negative = any(kw in norm for kw in H1B_NEGATIVE_KEYWORDS)

    if negative:
        # Explicit negative wins even if positive language appears
        return False
    if positive:
        return True
    return None   # unknown / not mentioned


# ---------------------------------------------------------------------------
# MAANG detection
# ---------------------------------------------------------------------------

def detect_maang(company_name: str, job_text: str = "") -> bool:
    """
    Determine if a job is at a MAANG company.

    Checks both the company name field and the job text (for cases where the
    posting lists subsidiaries or official legal names).

    Args:
        company_name: Company field from the job listing.
        job_text:     Full job description text (optional).

    Returns:
        True if the company is identified as MAANG, False otherwise.
    """
    search_corpus = _normalise(company_name + " " + job_text[:500])

    for alias in MAANG_ALIASES:
        # Match as a whole word to avoid false positives (e.g. "Amazonia")
        if re.search(rf"\b{re.escape(alias)}\b", search_corpus):
            return True
    return False


# ---------------------------------------------------------------------------
# Fortune 500 detection
# ---------------------------------------------------------------------------

def detect_fortune500(company_name: str) -> bool:
    """
    Check whether a company name matches the Fortune 500 list.

    Uses normalised substring matching to handle slight name variations
    (e.g. "JPMorgan Chase & Co." vs "jpmorgan").

    Args:
        company_name: Company field from the job listing.

    Returns:
        True if matched, False otherwise.
    """
    norm_name = _normalise(company_name)
    for f500 in FORTUNE_500_SET:
        if f500 in norm_name or norm_name in f500:
            return True
    return False


# ---------------------------------------------------------------------------
# Application portal detection
# ---------------------------------------------------------------------------

def detect_portal(job_url: str = "", job_text: str = "") -> str:
    """
    Identify the applicant tracking system / application portal.

    Checks both the job URL and text body for known portal domain signatures.

    Args:
        job_url:   URL of the job posting or application link.
        job_text:  Job description body text.

    Returns:
        Portal name string (e.g. "Workday", "Greenhouse") or "Unknown".
    """
    search_text = (job_url + " " + job_text[:1000]).lower()

    for portal_name, patterns in PORTAL_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in search_text:
                return portal_name

    return "Unknown"


# ---------------------------------------------------------------------------
# ATS keyword extraction
# ---------------------------------------------------------------------------

def extract_ats_keywords(job_text: str, resume_profile: dict) -> list[str]:
    """
    Extract ATS-critical keywords from the job description that are:
      - Present in the job posting
      - NOT already in the resume (i.e., gaps the applicant should add)
      plus keywords that ARE in both (good signals).

    Returns a combined list useful for ATS optimisation, sorted by
    frequency in the job text (most common first, up to 20).

    Args:
        job_text:       Full job description text.
        resume_profile: Output from Data_Extraction.extract_resume_keywords().

    Returns:
        List of keyword strings (lowercased).
    """
    norm_job = _normalise(job_text)
    resume_skills = set(resume_profile.get("all_keywords", []))

    # All known skill terms that appear in the job
    job_skill_hits: list[tuple[str, int]] = []
    all_known_skills = TECH_SKILLS_SET | SOFT_SKILLS_SET

    for skill in all_known_skills:
        pattern = rf"\b{re.escape(skill)}\b"
        occurrences = len(re.findall(pattern, norm_job))
        if occurrences > 0:
            job_skill_hits.append((skill, occurrences))

    # Sort descending by frequency, then alphabetically
    job_skill_hits.sort(key=lambda x: (-x[1], x[0]))

    # Return top-20 keywords
    return [skill for skill, _ in job_skill_hits[:20]]


# ---------------------------------------------------------------------------
# Job classification (combines all detectors)
# ---------------------------------------------------------------------------

def classify_job(job: dict, resume_profile: dict) -> dict:
    """
    Enrich a raw job dict with computed classification fields.

    Input job dict should have at minimum:
      - title       : str
      - company     : str
      - description : str
      - url         : str  (optional)
      - location    : str  (optional)
      - source      : str  (optional)
      - posted_date : str  (optional)

    Returns the job dict updated with:
      - match_score     : float (0-1)
      - match_pct       : float (0-100, rounded to 1dp)
      - h1b_sponsor     : bool | None
      - is_maang        : bool
      - is_fortune500   : bool
      - portal          : str
      - ats_keywords    : list[str]
      - key_skills      : list[str]  (resume skills found in this job)
      - above_threshold : bool
    """
    description = job.get("description", "")
    company     = job.get("company", "")
    url         = job.get("url", "")

    # Match score
    score = calculate_match_score(resume_profile, description)
    match_pct = round(score * 100, 1)

    # Classification signals
    h1b        = detect_h1b(description)
    is_maang   = detect_maang(company, description)
    is_f500    = detect_fortune500(company)
    portal     = detect_portal(url, description)
    ats_kw     = extract_ats_keywords(description, resume_profile)

    # Skills from resume that are explicitly mentioned in this job
    norm_desc = _normalise(description)
    resume_skills = set(resume_profile.get("all_keywords", []))
    key_skills = [
        s for s in resume_skills
        if re.search(rf"\b{re.escape(s)}\b", norm_desc)
    ]

    enriched = {
        **job,
        "match_score":     score,
        "match_pct":       match_pct,
        "h1b_sponsor":     h1b,
        "is_maang":        is_maang,
        "is_fortune500":   is_f500,
        "portal":          portal,
        "ats_keywords":    ats_kw,
        "key_skills":      sorted(key_skills),
        "above_threshold": score >= MATCH_THRESHOLD,
    }

    logger.debug(
        "Classified '%s' @ %s: %.1f%% match | H1B=%s | MAANG=%s | F500=%s | Portal=%s",
        job.get("title", "N/A"), company, match_pct,
        h1b, is_maang, is_f500, portal,
    )
    return enriched


# ---------------------------------------------------------------------------
# Batch processing helper
# ---------------------------------------------------------------------------

def classify_jobs_batch(jobs: list[dict], resume_profile: dict) -> list[dict]:
    """
    Classify a list of jobs and return only those meeting the match threshold.

    Args:
        jobs:           List of raw job dicts from the scraper.
        resume_profile: Output from Data_Extraction.load_resume().

    Returns:
        List of enriched job dicts where above_threshold is True,
        sorted descending by match_pct.
    """
    enriched: list[dict] = []
    for job in jobs:
        try:
            classified = classify_job(job, resume_profile)
            enriched.append(classified)
        except Exception as exc:
            logger.warning(
                "Failed to classify job '%s': %s",
                job.get("title", "unknown"), exc,
            )

    qualified = [j for j in enriched if j["above_threshold"]]
    qualified.sort(key=lambda j: j["match_pct"], reverse=True)

    logger.info(
        "Batch classification: %d jobs -> %d above %.0f%% threshold.",
        len(jobs), len(qualified), MATCH_THRESHOLD * 100,
    )
    return qualified
