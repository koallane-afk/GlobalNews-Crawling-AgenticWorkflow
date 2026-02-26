#!/usr/bin/env python3
"""Extract architecture-relevant sections from PRD.

Usage:
    python3 scripts/filter_prd_architecture.py --project-dir .
    python3 scripts/filter_prd_architecture.py --project-dir . --prd coding-resource/PRD.md

Output: Filtered PRD sections to planning/prd-architecture-extract.md

This is a P1 pre-processing script: deterministic extraction, no LLM inference.
It extracts sections 6 (System Architecture), 7 (Output Specs / Data Schemas),
and 8 (Tech Stack) from the PRD document using heading-level regex to isolate
sections. The system-architect agent receives only the architecture-relevant
content instead of the entire PRD.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any


def _emit(result: dict[str, Any]) -> None:
    """Print JSON result to stdout and exit."""
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    sys.exit(0 if result.get("valid") else 1)


def _extract_sections(
    content: str,
    target_sections: list[int],
) -> dict[int, str]:
    """Extract top-level sections (## N. ...) by section number.

    Sections are delimited by level-2 headings (## N.) and end at the next
    level-2 heading or end of file.

    Args:
        content: Full PRD markdown content.
        target_sections: List of section numbers to extract (e.g., [6, 7, 8]).

    Returns:
        Dict mapping section number to its full text (including the heading).
    """
    lines = content.splitlines(keepends=True)
    # Pattern: ## N. Title  or  ## N Title  (with optional leading #)
    heading_re = re.compile(r"^##\s+(\d+)\.?\s")

    # Find the line indices where each section starts
    section_starts: list[tuple[int, int]] = []  # (section_number, line_index)
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            section_starts.append((int(m.group(1)), i))

    # Extract target sections
    result: dict[int, str] = {}
    for idx, (sec_num, start_line) in enumerate(section_starts):
        if sec_num not in target_sections:
            continue
        # End is the start of the next section or end of file
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][1]
        else:
            end_line = len(lines)
        section_text = "".join(lines[start_line:end_line])
        result[sec_num] = section_text

    return result


def _extract_constraints(content: str) -> str | None:
    """Extract the Hard Constraints table from the PRD intro.

    This is a small but critical section (C1-C5) that architects need.
    It appears early in the document, before section 1.
    """
    lines = content.splitlines(keepends=True)
    in_constraints = False
    constraint_lines: list[str] = []

    for line in lines:
        # Detect the constraints section header
        if re.search(r"핵심 제약 조건|Hard Constraints", line, re.IGNORECASE):
            in_constraints = True
            constraint_lines.append(line)
            continue
        if in_constraints:
            # End at the next major heading or horizontal rule after table
            if re.match(r"^---\s*$", line) and len(constraint_lines) > 3:
                break
            if re.match(r"^##\s+\d+\.", line):
                break
            constraint_lines.append(line)

    if len(constraint_lines) > 2:
        return "".join(constraint_lines)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract architecture-relevant sections (6, 7, 8) from PRD."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Root directory of the project.",
    )
    parser.add_argument(
        "--prd",
        default="coding-resource/PRD.md",
        help="Path to PRD.md relative to project-dir.",
    )
    parser.add_argument(
        "--output",
        default="planning/prd-architecture-extract.md",
        help="Output path relative to project-dir.",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    if not os.path.isdir(project_dir):
        _emit({"valid": False, "error": f"Project directory not found: {project_dir}"})

    prd_path = os.path.join(project_dir, args.prd)
    output_path = os.path.join(project_dir, args.output)

    if not os.path.isfile(prd_path):
        _emit({
            "valid": False,
            "error": f"PRD file not found: {prd_path}",
            "hint": "Ensure coding-resource/PRD.md exists in the project.",
        })

    with open(prd_path, encoding="utf-8") as f:
        content = f.read()

    # Extract target sections
    target_nums = [6, 7, 8]
    sections = _extract_sections(content, target_nums)

    missing = [n for n in target_nums if n not in sections]
    if missing:
        _emit({
            "valid": False,
            "error": f"Missing PRD sections: {missing}",
            "hint": "PRD must contain ## 6. , ## 7. , ## 8.  headings.",
            "found_sections": list(sections.keys()),
        })

    # Also extract constraints (small but essential for architecture)
    constraints = _extract_constraints(content)

    # Section metadata
    section_meta: dict[str, dict[str, Any]] = {}
    for num, text in sections.items():
        lines = text.splitlines()
        section_meta[f"section_{num}"] = {
            "lines": len(lines),
            "words": len(text.split()),
            "heading": lines[0].strip() if lines else "",
        }

    # Build the filtered document
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts: list[str] = [
        f"# PRD Architecture Extract\n\n",
        f"> **Generated**: {now}\n",
        f"> **Source**: `{args.prd}`\n",
        f"> **Extracted sections**: 6 (System Architecture), "
        f"7 (Output Specs / Data Schemas), 8 (Tech Stack)\n",
        f"> **Purpose**: Focused input for system-architect agent (Step 5)\n\n",
    ]

    if constraints:
        parts.append("---\n\n")
        parts.append("## Hard Constraints (from PRD intro)\n\n")
        parts.append(constraints)
        parts.append("\n\n")

    for num in target_nums:
        parts.append("---\n\n")
        parts.append(sections[num])
        if not sections[num].endswith("\n"):
            parts.append("\n")

    filtered = "".join(parts)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(filtered)

    _emit({
        "valid": True,
        "output_path": output_path,
        "sections_extracted": target_nums,
        "constraints_included": constraints is not None,
        "section_meta": section_meta,
        "total_lines": len(filtered.splitlines()),
        "total_words": len(filtered.split()),
    })


if __name__ == "__main__":
    main()
