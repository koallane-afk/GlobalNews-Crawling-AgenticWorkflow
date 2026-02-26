#!/usr/bin/env python3
"""Merge Step 1 and Step 2 outputs for crawl-analyst context.

Usage:
    python3 scripts/merge_recon_and_deps.py --project-dir .

Output: Combined context file at research/merged-recon-deps.md

This is a P1 pre-processing script: deterministic extraction, no LLM inference.
It reads the Step 1 site reconnaissance output and Step 2 tech validation output,
then produces a single merged document that the Step 3 crawl-analyst agent can
consume as focused input.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any


def _emit(result: dict[str, Any]) -> None:
    """Print JSON result to stdout and exit."""
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    sys.exit(0 if result.get("valid") else 1)


def _read_file(path: str) -> str | None:
    """Read a file and return its content, or None if it does not exist."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_summary_stats(content: str) -> dict[str, Any]:
    """Extract basic statistics from a markdown document.

    Returns line count, heading count, and approximate word count.
    These help the consuming agent gauge document depth at a glance.
    """
    lines = content.splitlines()
    headings = [ln for ln in lines if ln.startswith("#")]
    words = len(content.split())
    return {
        "lines": len(lines),
        "headings": len(headings),
        "words": words,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Step 1 (site recon) + Step 2 (tech validation) for Step 3 agent."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Root directory of the project.",
    )
    parser.add_argument(
        "--recon",
        default="research/site-reconnaissance.md",
        help="Path to Step 1 output relative to project-dir.",
    )
    parser.add_argument(
        "--tech",
        default="research/tech-validation.md",
        help="Path to Step 2 output relative to project-dir.",
    )
    parser.add_argument(
        "--output",
        default="research/merged-recon-deps.md",
        help="Output path relative to project-dir.",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    if not os.path.isdir(project_dir):
        _emit({"valid": False, "error": f"Project directory not found: {project_dir}"})

    recon_path = os.path.join(project_dir, args.recon)
    tech_path = os.path.join(project_dir, args.tech)
    output_path = os.path.join(project_dir, args.output)

    # Read source files
    recon_content = _read_file(recon_path)
    tech_content = _read_file(tech_path)

    errors: list[str] = []
    if recon_content is None:
        errors.append(f"Step 1 output not found: {recon_path}")
    if tech_content is None:
        errors.append(f"Step 2 output not found: {tech_path}")

    if errors:
        _emit({
            "valid": False,
            "errors": errors,
            "hint": "Ensure Steps 1 and 2 are completed before running this script.",
        })

    # At this point both are guaranteed non-None
    assert recon_content is not None
    assert tech_content is not None

    recon_stats = _extract_summary_stats(recon_content)
    tech_stats = _extract_summary_stats(tech_content)

    # Build the merged document
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    merged = f"""\
# Merged Context: Site Reconnaissance + Technology Validation

> **Generated**: {now}
> **Purpose**: Combined input for Step 3 (Crawling Feasibility Analysis) agent.
> **Source files**: `{args.recon}` + `{args.tech}`

## Document Statistics

| Source | Lines | Headings | Words |
|--------|-------|----------|-------|
| Site Reconnaissance (Step 1) | {recon_stats['lines']} | {recon_stats['headings']} | {recon_stats['words']} |
| Tech Validation (Step 2) | {tech_stats['lines']} | {tech_stats['headings']} | {tech_stats['words']} |

---

## Part 1: Site Reconnaissance (Step 1)

> From `{args.recon}` — Contains per-site analysis of all 44 target news sites:
> RSS/sitemap availability, dynamic loading detection, bot-blocking level,
> section count, and crawling difficulty tier classification.

{recon_content}

---

## Part 2: Technology Stack Validation (Step 2)

> From `{args.tech}` — Contains dependency installation results, Korean NLP
> model benchmarks (Kiwi, KoBERT, KcELECTRA, KLUE-RoBERTa, BERTopic),
> and memory profiling for M2 Pro 16GB.

{tech_content}

---

## Cross-Reference Guide for Step 3 Agent

Use this guide to connect reconnaissance findings to technology capabilities:

1. **Sites requiring Playwright/Patchright** (dynamic loading = Yes in Part 1)
   - Verify Playwright install status in Part 2 dependency validation
   - Check memory overhead of browser instances in Part 2 memory profile

2. **Sites with paywall detection** (paywall = Yes in Part 1)
   - Check undetected-chromedriver availability in Part 2
   - Plan Tier 4-5 escalation strategies accordingly

3. **Sites with extreme bot-blocking** (blocking = high/extreme in Part 1)
   - Verify Patchright + fingerprint-suite in Part 2
   - These sites need the full 6-Tier escalation chain

4. **Korean sites** (language = ko in Part 1)
   - Use Kiwi morphological analysis benchmarks from Part 2
   - Verify KoBERT/KcELECTRA availability for downstream sentiment analysis

5. **Daily article volume estimates** (from Part 1) vs **processing capacity**
   (from Part 2 benchmarks) — ensure the pipeline can process daily volume
   within the 30-minute/1K-article target.
"""

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(merged)

    _emit({
        "valid": True,
        "output_path": output_path,
        "recon_stats": recon_stats,
        "tech_stats": tech_stats,
        "total_merged_lines": len(merged.splitlines()),
    })


if __name__ == "__main__":
    main()
