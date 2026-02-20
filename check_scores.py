#!/usr/bin/env python3
"""Check match scores for demo jobs."""

from Data_Extraction import load_resume
from brain import classify_jobs_batch
from orchestrator import generate_demo_jobs

print("Loading resume...")
resume = load_resume("Pragati_Khekale_DS_GL.pdf")

print("Generating demo jobs...")
jobs = generate_demo_jobs()

print("Classifying all jobs (no threshold filter)...")
from brain import classify_job
for job in jobs:
    classified = classify_job(job, resume)
    print(f"{classified['match_pct']:5.1f}%  {classified['title']:40s}  @  {classified['company']:20s}  H1B={str(classified['h1b_sponsor']):6s}  MAANG={classified['is_maang']}")
