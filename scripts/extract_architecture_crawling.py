#!/usr/bin/env python3
"""Extract crawling architecture from blueprint for crawl-engine-team.

Usage: python3 scripts/extract_architecture_crawling.py --project-dir .

Reads:
  - planning/architecture-blueprint.md   (Step 5 output)
  - planning/crawling-strategies.md      (Step 6 output)

Output:
  - planning/team-input/crawling-architecture.md

Extracts the crawling layer architecture, interfaces (SiteAdapter,
NetworkGuard), data contracts, and includes relevant strategy summary
from Step 6 so the crawl-engine-team can work autonomously.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Section extraction helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


def _extract_sections_by_keywords(
    text: str, keywords: list[str], *, heading_level_max: int = 4
) -> list[str]:
    """Return full text blocks whose heading contains any of *keywords*.

    Captures from the matching heading until the next heading of equal or
    higher level (or EOF).
    """
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        return []

    results: list[str] = []
    lower_keywords = [k.lower() for k in keywords]

    for idx, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()

        if level > heading_level_max:
            continue

        if not any(kw in title.lower() for kw in lower_keywords):
            continue

        start = match.start()
        # Find the end: next heading of equal or higher level
        end = len(text)
        for subsequent in headings[idx + 1 :]:
            if len(subsequent.group(1)) <= level:
                end = subsequent.start()
                break

        results.append(text[start:end].rstrip())

    return results


def _extract_code_blocks(text: str, *, lang_filter: str | None = None) -> list[str]:
    """Extract fenced code blocks, optionally filtered by language tag."""
    pattern = r"```(\w*)\n(.*?)```"
    blocks: list[str] = []
    for m in re.finditer(pattern, text, re.DOTALL):
        lang = m.group(1).lower()
        if lang_filter and lang != lang_filter.lower():
            continue
        blocks.append(m.group(0))
    return blocks


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def extract_crawling_architecture(project_dir: Path) -> dict:
    """Extract and assemble crawling architecture document.

    Returns a dict with 'valid', 'output_path', and diagnostic info.
    """
    blueprint_path = project_dir / "planning" / "architecture-blueprint.md"
    strategies_path = project_dir / "planning" / "crawling-strategies.md"
    output_dir = project_dir / "planning" / "team-input"
    output_path = output_dir / "crawling-architecture.md"

    errors: list[str] = []

    # ------------------------------------------------------------------
    # Read source files
    # ------------------------------------------------------------------
    blueprint_text = ""
    if blueprint_path.is_file():
        blueprint_text = blueprint_path.read_text(encoding="utf-8")
    else:
        errors.append(f"Blueprint not found: {blueprint_path}")

    strategies_text = ""
    if strategies_path.is_file():
        strategies_text = strategies_path.read_text(encoding="utf-8")
    else:
        errors.append(f"Strategies not found: {strategies_path}")

    if not blueprint_text and not strategies_text:
        return {
            "valid": False,
            "errors": errors,
            "output_path": str(output_path),
            "sections_extracted": 0,
        }

    # ------------------------------------------------------------------
    # Extract crawling-related sections from blueprint
    # ------------------------------------------------------------------
    crawling_keywords = [
        "crawl",
        "crawler",
        "scraping",
        "scraper",
        "spider",
        "site adapter",
        "siteadapter",
        "network guard",
        "networkguard",
        "rate limit",
        "ratelimit",
        "anti-block",
        "antiblock",
        "fetcher",
        "fetch",
        "http client",
        "request",
        "adapter",
    ]

    interface_keywords = [
        "interface",
        "abstract",
        "protocol",
        "contract",
        "schema",
        "data model",
        "type",
    ]

    crawling_sections = _extract_sections_by_keywords(
        blueprint_text, crawling_keywords
    )
    interface_sections = _extract_sections_by_keywords(
        blueprint_text, interface_keywords
    )
    code_blocks = _extract_code_blocks(blueprint_text, lang_filter="python")

    # Extract strategy summary from Step 6
    strategy_keywords = [
        "strategy",
        "approach",
        "method",
        "technique",
        "summary",
        "overview",
        "classification",
        "site group",
        "tier",
    ]
    strategy_sections = _extract_sections_by_keywords(
        strategies_text, strategy_keywords
    )

    # ------------------------------------------------------------------
    # Assemble output document
    # ------------------------------------------------------------------
    parts: list[str] = []
    parts.append("# Crawling Architecture — Team Input Document")
    parts.append("")
    parts.append("> Auto-generated by `extract_architecture_crawling.py`")
    parts.append(f"> Source: `{blueprint_path}` + `{strategies_path}`")
    parts.append("")

    # Part 1: Crawling layer architecture
    parts.append("## 1. Crawling Layer Architecture")
    parts.append("")
    if crawling_sections:
        for section in crawling_sections:
            parts.append(section)
            parts.append("")
    else:
        parts.append("_No crawling-specific sections found in blueprint._")
        parts.append("")

    # Part 2: Interfaces and data contracts
    parts.append("## 2. Interfaces & Data Contracts")
    parts.append("")
    if interface_sections:
        for section in interface_sections:
            parts.append(section)
            parts.append("")
    else:
        parts.append("_No interface/contract sections found in blueprint._")
        parts.append("")

    # Part 3: Relevant code snippets
    if code_blocks:
        parts.append("## 3. Code Snippets (from Blueprint)")
        parts.append("")
        for block in code_blocks:
            parts.append(block)
            parts.append("")

    # Part 4: Strategy summary from Step 6
    parts.append("## 4. Crawling Strategy Summary (from Step 6)")
    parts.append("")
    if strategy_sections:
        for section in strategy_sections:
            parts.append(section)
            parts.append("")
    else:
        parts.append("_No strategy sections found in crawling-strategies.md._")
        parts.append("")

    output_text = "\n".join(parts)

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")

    sections_extracted = (
        len(crawling_sections)
        + len(interface_sections)
        + len(code_blocks)
        + len(strategy_sections)
    )

    result = {
        "valid": True,
        "output_path": str(output_path),
        "sections_extracted": sections_extracted,
        "crawling_sections": len(crawling_sections),
        "interface_sections": len(interface_sections),
        "code_blocks": len(code_blocks),
        "strategy_sections": len(strategy_sections),
        "output_size_bytes": len(output_text.encode("utf-8")),
        "warnings": errors if errors else [],
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract crawling architecture from blueprint for crawl-engine-team."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = extract_crawling_architecture(project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
