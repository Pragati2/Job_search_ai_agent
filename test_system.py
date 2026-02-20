#!/usr/bin/env python3
"""Quick test script to verify the system."""

import json
import sys

print("Testing Data_Extraction.py...")
from Data_Extraction import load_resume
profile = load_resume("Pragati_Khekale_DS_GL.pdf")
summary = {k: v for k, v in profile.items() if k != "raw_text"}
print("✓ Data_Extraction.py OK")
print(json.dumps(summary, indent=2))

print("\nTesting brain.py...")
from brain import calculate_match_score, classify_job, detect_h1b, detect_maang

# Test H1B detection
assert detect_h1b("We sponsor H1B visas") is True
assert detect_h1b("No sponsorship available") is False
assert detect_h1b("Looking for a data scientist") is None
print("✓ H1B detection OK")

# Test MAANG detection
assert detect_maang("Google", "") is True
assert detect_maang("Meta", "") is True
assert detect_maang("Amazon", "") is True
assert detect_maang("Acme Corp", "") is False
print("✓ MAANG detection OK")

# Test match score
test_job = {
    "title": "Data Scientist",
    "company": "Test Co",
    "description": "Python machine learning SQL pandas statistics",
    "url": "https://example.com",
}
score = calculate_match_score(profile, test_job["description"])
print(f"✓ Match score calculation OK (sample score: {score:.3f})")

# Test classification
classified = classify_job(test_job, profile)
print(f"✓ Job classification OK (match_pct: {classified['match_pct']:.1f}%)")

print("\nAll tests passed!")
