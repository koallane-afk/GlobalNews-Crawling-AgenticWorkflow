#!/usr/bin/env python3
"""Extract analysis-relevant sections from PRD.

Usage:
    python3 scripts/filter_prd_analysis.py --project-dir .
    python3 scripts/filter_prd_analysis.py --project-dir . --prd coding-resource/PRD.md

Output: Filtered PRD sections to planning/prd-analysis-extract.md

This is a P1 pre-processing script: deterministic extraction, no LLM inference.
It extracts the analysis engine section (5.2) from the PRD, including:
  - 56 analysis techniques (5.2.1)
  - 8-Stage analysis pipeline (5.2.2)
  - 5-Layer signal detection hierarchy (5.2.3)
  - Singularity detection (5.2.4)
  - Korean NLP optimal stack (5.2.5)

The pipeline-designer agent receives only analysis-relevant content.
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


def _extract_section_range(
    content: str,
    start_pattern: str,
    end_pattern: str,
    include_start: bool = True,
) -> str | None:
    """Extract text between two heading patterns.

    Args:
        content: Full document text.
        start_pattern: Regex pattern for the starting heading.
        end_pattern: Regex pattern for the ending heading (exclusive).
        include_start: Whether to include the start heading line.

    Returns:
        Extracted text, or None if start pattern is not found.
    """
    lines = content.splitlines(keepends=True)
    start_re = re.compile(start_pattern)
    end_re = re.compile(end_pattern)

    start_idx: int | None = None
    end_idx: int | None = None

    for i, line in enumerate(lines):
        if start_idx is None and start_re.match(line):
            start_idx = i if include_start else i + 1
        elif start_idx is not None and end_re.match(line):
            end_idx = i
            break

    if start_idx is None:
        return None

    if end_idx is None:
        end_idx = len(lines)

    return "".join(lines[start_idx:end_idx])


def _extract_subsections(content: str, parent_num: str) -> list[dict[str, Any]]:
    """Extract metadata about subsections under a parent section.

    For example, parent_num="5.2" will find 5.2.1, 5.2.2, etc.
    """
    lines = content.splitlines()
    # Match ### 5.2.N or #### 5.2.N headings
    pattern = re.compile(rf"^#{{2,4}}\s+{re.escape(parent_num)}\.(\d+)\s+(.*)")
    subsections: list[dict[str, Any]] = []
    for line in lines:
        m = pattern.match(line)
        if m:
            subsections.append({
                "number": f"{parent_num}.{m.group(1)}",
                "title": m.group(2).strip(),
            })
    return subsections


def _count_techniques(content: str) -> int:
    """Count the number of analysis techniques mentioned in the technique table.

    Looks for the technique summary table in section 5.2.1 and sums the
    technique counts per domain row.
    """
    total = 0
    # Match rows like: | **텍스트 처리·특성 추출** | 12 | ...
    count_re = re.compile(r"\|\s*\*?\*?[^|]+\*?\*?\s*\|\s*(\d+)\s*\|")
    in_table = False
    for line in content.splitlines():
        if "기법 수" in line or "Technique" in line:
            in_table = True
            continue
        if in_table and "|" in line:
            m = count_re.match(line)
            if m:
                total += int(m.group(1))
        elif in_table and not line.strip():
            # Empty line after table
            if total > 0:
                break
    return total


def _count_stages(content: str) -> int:
    """Count the number of stages in the 8-Stage pipeline description."""
    stage_re = re.compile(r"Stage\s+(\d+):", re.IGNORECASE)
    stages: set[int] = set()
    for m in stage_re.finditer(content):
        stages.add(int(m.group(1)))
    return len(stages)


def _count_layers(content: str) -> int:
    """Count the number of layers in the 5-Layer signal hierarchy."""
    layer_re = re.compile(r"\*\*L(\d+)\*\*")
    layers: set[int] = set()
    for m in layer_re.finditer(content):
        layers.add(int(m.group(1)))
    return len(layers)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract analysis-relevant sections from PRD for pipeline-designer agent."
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
        default="planning/prd-analysis-extract.md",
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

    # -- Extract Section 5.2 (Analysis Engine) --------------------------------
    # Section 5.2 starts at "### 5.2" and ends at "## 6." (next top-level section)
    analysis_section = _extract_section_range(
        content,
        start_pattern=r"^###?\s+5\.2\s",
        end_pattern=r"^##\s+6\.\s",
    )

    if analysis_section is None:
        # Fallback: try to extract the entire section 5
        analysis_section = _extract_section_range(
            content,
            start_pattern=r"^##\s+5\.\s",
            end_pattern=r"^##\s+6\.\s",
        )

    if analysis_section is None:
        _emit({
            "valid": False,
            "error": "Could not find PRD section 5.2 (Analysis Engine).",
            "hint": "PRD must contain '### 5.2' or '## 5.' heading.",
        })

    # At this point analysis_section is guaranteed non-None
    assert analysis_section is not None

    # -- Also extract Parquet schema section from 7.1 for output reference ----
    parquet_section = _extract_section_range(
        content,
        start_pattern=r"^###?\s+7\.1\s",
        end_pattern=r"^###?\s+7\.2\s",
    )

    # -- Also extract the constraints table (C1-C5) --------------------------
    constraints_section = _extract_section_range(
        content,
        start_pattern=r"^###?\s+핵심 제약",
        end_pattern=r"^---\s*$",
    )

    # -- Gather statistics ---------------------------------------------------
    subsections = _extract_subsections(analysis_section, "5.2")
    technique_count = _count_techniques(analysis_section)
    stage_count = _count_stages(analysis_section)
    layer_count = _count_layers(analysis_section)

    # -- Build the filtered document -----------------------------------------
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts: list[str] = [
        "# PRD Analysis Engine Extract\n\n",
        f"> **Generated**: {now}\n",
        f"> **Source**: `{args.prd}`\n",
        "> **Extracted**: Section 5.2 (Analysis Engine) with all subsections\n",
        "> **Purpose**: Focused input for pipeline-designer agent (Step 7)\n\n",
        "## Extraction Summary\n\n",
        f"- **Subsections found**: {len(subsections)}\n",
    ]
    for ss in subsections:
        parts.append(f"  - {ss['number']}: {ss['title']}\n")
    parts.append(f"- **Analysis techniques counted**: {technique_count}\n")
    parts.append(f"- **Pipeline stages found**: {stage_count}\n")
    parts.append(f"- **Signal layers found**: {layer_count}\n\n")

    if constraints_section:
        parts.append("---\n\n")
        parts.append("## Hard Constraints (Pipeline-Relevant)\n\n")
        parts.append("> C1 (Claude API = $0) and C3 (MacBook M2 Pro 16GB) directly\n")
        parts.append("> constrain analysis pipeline design choices.\n\n")
        parts.append(constraints_section)
        parts.append("\n\n")

    parts.append("---\n\n")
    parts.append(analysis_section)
    if not analysis_section.endswith("\n"):
        parts.append("\n")

    if parquet_section:
        parts.append("\n---\n\n")
        parts.append("## Output Schema Reference (PRD 7.1 — Parquet)\n\n")
        parts.append("> The pipeline-designer must ensure each stage's output columns\n")
        parts.append("> align with these Parquet schema definitions.\n\n")
        parts.append(parquet_section)
        if not parquet_section.endswith("\n"):
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
        "subsections": subsections,
        "technique_count": technique_count,
        "stage_count": stage_count,
        "layer_count": layer_count,
        "parquet_schema_included": parquet_section is not None,
        "constraints_included": constraints_section is not None,
        "total_lines": len(filtered.splitlines()),
        "total_words": len(filtered.split()),
    })


if __name__ == "__main__":
    main()
