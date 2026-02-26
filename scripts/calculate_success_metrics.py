#!/usr/bin/env python3
"""Calculate PRD SS9.1 success metrics from test results.

Usage: python3 scripts/calculate_success_metrics.py --project-dir .

Reads:
  - testing/per-site-results.json

Output:
  - testing/success-metrics.json

Reads per-site test results JSON, calculates success metrics, and
compares against PRD thresholds:
  - success_rate:  >=80% of sites with >0 articles
  - total_articles: >=500
  - dedup_effectiveness: >=90%
  - avg_crawl_time_per_site: <=5 min (300 sec)
  - peak_memory: <=10 GB

Outputs pass/fail per metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# PRD thresholds
# ---------------------------------------------------------------------------

_THRESHOLDS: dict[str, dict[str, Any]] = {
    "success_rate": {
        "description": "Percentage of sites with >0 articles crawled",
        "threshold": 80.0,
        "unit": "%",
        "comparator": ">=",
    },
    "total_articles": {
        "description": "Total articles crawled across all sites",
        "threshold": 500,
        "unit": "articles",
        "comparator": ">=",
    },
    "dedup_effectiveness": {
        "description": "Deduplication effectiveness rate",
        "threshold": 90.0,
        "unit": "%",
        "comparator": ">=",
    },
    "avg_crawl_time_per_site": {
        "description": "Average crawl time per site",
        "threshold": 300.0,
        "unit": "seconds",
        "comparator": "<=",
    },
    "peak_memory": {
        "description": "Peak memory usage during crawl",
        "threshold": 10.0,
        "unit": "GB",
        "comparator": "<=",
    },
}

_TOTAL_SITES = 44


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def _compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute all success metrics from per-site results.

    Expected per-site result structure:
    {
        "domain": "example.com",
        "articles_crawled": 25,
        "articles_before_dedup": 30,
        "articles_after_dedup": 25,
        "crawl_time_seconds": 120.5,
        "memory_peak_gb": 1.2,
        "status": "success" | "error" | "timeout",
        "errors": []
    }
    """
    if not results:
        return {
            "success_rate": 0.0,
            "total_articles": 0,
            "avg_articles_per_site": 0.0,
            "dedup_effectiveness": 0.0,
            "avg_crawl_time_per_site": 0.0,
            "peak_memory": 0.0,
            "sites_tested": 0,
            "sites_successful": 0,
        }

    sites_tested = len(results)
    sites_with_articles = sum(
        1 for r in results
        if r.get("articles_crawled", r.get("articles_after_dedup", 0)) > 0
    )

    # Success rate: sites with >0 articles / total expected sites (44)
    total_expected = max(sites_tested, _TOTAL_SITES)
    success_rate = (sites_with_articles / total_expected) * 100.0

    # Total articles (after dedup)
    total_articles = sum(
        r.get("articles_crawled", r.get("articles_after_dedup", 0))
        for r in results
    )

    # Average articles per successful site
    avg_articles = (
        total_articles / sites_with_articles
        if sites_with_articles > 0
        else 0.0
    )

    # Dedup effectiveness
    total_before_dedup = sum(
        r.get("articles_before_dedup", r.get("articles_crawled", 0))
        for r in results
    )
    total_after_dedup = sum(
        r.get("articles_after_dedup", r.get("articles_crawled", 0))
        for r in results
    )
    duplicates_removed = total_before_dedup - total_after_dedup
    dedup_effectiveness = (
        (duplicates_removed / total_before_dedup) * 100.0
        if total_before_dedup > 0 and duplicates_removed >= 0
        else 0.0
    )
    # If no dedup data available (before == after), report as N/A
    has_dedup_data = any(
        r.get("articles_before_dedup", 0) != r.get("articles_after_dedup", 0)
        or r.get("articles_before_dedup", 0) > 0
        for r in results
    )

    # Average crawl time per site
    crawl_times = [
        r.get("crawl_time_seconds", 0.0)
        for r in results
        if r.get("crawl_time_seconds", 0.0) > 0
    ]
    avg_crawl_time = (
        sum(crawl_times) / len(crawl_times)
        if crawl_times
        else 0.0
    )

    # Peak memory
    memory_peaks = [
        r.get("memory_peak_gb", 0.0)
        for r in results
        if r.get("memory_peak_gb", 0.0) > 0
    ]
    peak_memory = max(memory_peaks) if memory_peaks else 0.0

    return {
        "success_rate": round(success_rate, 2),
        "total_articles": total_articles,
        "avg_articles_per_site": round(avg_articles, 2),
        "dedup_effectiveness": round(dedup_effectiveness, 2) if has_dedup_data else None,
        "avg_crawl_time_per_site": round(avg_crawl_time, 2),
        "peak_memory": round(peak_memory, 3),
        "sites_tested": sites_tested,
        "sites_successful": sites_with_articles,
        "total_before_dedup": total_before_dedup,
        "total_after_dedup": total_after_dedup,
    }


def _evaluate_thresholds(
    metrics: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Evaluate each metric against PRD thresholds.

    Returns a dict of metric_name -> {value, threshold, pass, comparator, ...}.
    """
    evaluations: dict[str, dict[str, Any]] = {}

    for metric_name, spec in _THRESHOLDS.items():
        value = metrics.get(metric_name)
        threshold = spec["threshold"]
        comparator = spec["comparator"]

        if value is None:
            evaluations[metric_name] = {
                "value": None,
                "threshold": threshold,
                "comparator": comparator,
                "unit": spec["unit"],
                "description": spec["description"],
                "pass": False,
                "note": "No data available",
            }
            continue

        if comparator == ">=":
            passed = value >= threshold
        elif comparator == "<=":
            passed = value <= threshold
        else:
            passed = value == threshold

        evaluations[metric_name] = {
            "value": value,
            "threshold": threshold,
            "comparator": comparator,
            "unit": spec["unit"],
            "description": spec["description"],
            "pass": passed,
        }

    return evaluations


# ---------------------------------------------------------------------------
# Per-site breakdown
# ---------------------------------------------------------------------------

def _per_site_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a condensed per-site summary for the output."""
    summary: list[dict[str, Any]] = []
    for r in results:
        domain = r.get("domain", "unknown")
        articles = r.get("articles_crawled", r.get("articles_after_dedup", 0))
        status = r.get("status", "unknown")
        crawl_time = r.get("crawl_time_seconds", 0.0)
        error_count = len(r.get("errors", []))

        summary.append({
            "domain": domain,
            "articles": articles,
            "status": status,
            "crawl_time_seconds": round(crawl_time, 2),
            "errors": error_count,
        })

    return sorted(summary, key=lambda x: x["domain"])


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def calculate_metrics(project_dir: Path) -> dict:
    """Calculate success metrics from per-site test results.

    Returns a dict with metrics, evaluations, and diagnostics.
    """
    input_path = project_dir / "testing" / "per-site-results.json"
    output_dir = project_dir / "testing"
    output_path = output_dir / "success-metrics.json"

    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Read per-site results
    # ------------------------------------------------------------------
    if not input_path.is_file():
        return {
            "valid": False,
            "errors": [f"Per-site results not found: {input_path}"],
            "output_path": str(output_path),
            "metrics": {},
            "evaluations": {},
        }

    try:
        raw = input_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [f"Invalid JSON in {input_path}: {e}"],
            "output_path": str(output_path),
            "metrics": {},
            "evaluations": {},
        }

    # Support both list and dict-with-results-key formats
    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = data.get("results", data.get("sites", []))
        if not isinstance(results, list):
            results = []
    else:
        return {
            "valid": False,
            "errors": [f"Unexpected data format in {input_path}"],
            "output_path": str(output_path),
            "metrics": {},
            "evaluations": {},
        }

    if not results:
        warnings.append("No site results found in input file")

    # ------------------------------------------------------------------
    # Compute metrics
    # ------------------------------------------------------------------
    metrics = _compute_metrics(results)
    evaluations = _evaluate_thresholds(metrics)

    # Overall pass/fail
    all_passed = all(e["pass"] for e in evaluations.values())
    total_pass = sum(1 for e in evaluations.values() if e["pass"])
    total_metrics = len(evaluations)

    # ------------------------------------------------------------------
    # Build output
    # ------------------------------------------------------------------
    output_doc = {
        "overall_pass": all_passed,
        "pass_count": total_pass,
        "total_metrics": total_metrics,
        "metrics": metrics,
        "evaluations": evaluations,
        "per_site_summary": _per_site_summary(results),
        "prd_reference": "PRD SS9.1",
    }

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = {
        "valid": True,
        "output_path": str(output_path),
        "overall_pass": all_passed,
        "pass_count": total_pass,
        "total_metrics": total_metrics,
        "metrics": metrics,
        "evaluations": {
            name: {"pass": e["pass"], "value": e["value"], "threshold": e["threshold"]}
            for name, e in evaluations.items()
        },
        "warnings": warnings,
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate PRD SS9.1 success metrics from test results."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = calculate_metrics(project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
