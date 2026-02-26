#!/usr/bin/env python3
"""Extract a specific step's guide from ORCHESTRATOR-PLAYBOOK.md.

Provides focused context injection for agents — instead of loading the
entire 1000+ line playbook, extract only the relevant step section.

Usage:
    python3 scripts/extract_orchestrator_step_guide.py --step 12 --project-dir .
    python3 scripts/extract_orchestrator_step_guide.py --step 12 --project-dir . --include-universal
    python3 scripts/extract_orchestrator_step_guide.py --step 12 --project-dir . --include-failure-recovery

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import re
import sys


# Step heading patterns in the playbook
# Matches: ### Step 1: ..., ### Step 10: ..., ### Step 20: ...
_STEP_HEADING_RE = re.compile(r"^### Step (\d+):")

# Section boundary: next step heading or phase heading
_SECTION_BOUNDARY_RE = re.compile(r"^##[#]? (?:Step \d+:|.*Phase)")

# Universal protocol section
_UNIVERSAL_HEADING = "### Universal Step Protocol"
_UNIVERSAL_END_RE = re.compile(r"^---$")

# Failure recovery section
_FAILURE_HEADING = "## Failure Recovery Reference"
_TEAM_MGMT_HEADING = "## Team Management Reference"


def extract_step_guide(playbook_path, step_num, include_universal=False, include_failure=False):
    """Extract a specific step's guide section from the playbook."""
    result = {
        "valid": True,
        "step": step_num,
        "content": "",
        "sections_included": [],
        "warnings": [],
    }

    if not os.path.exists(playbook_path):
        result["valid"] = False
        result["error"] = f"Playbook not found: {playbook_path}"
        return result

    with open(playbook_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # --- Extract target step section ---
    step_start = None
    step_end = None
    for i, line in enumerate(lines):
        m = _STEP_HEADING_RE.match(line)
        if m and int(m.group(1)) == step_num:
            step_start = i
            continue
        if step_start is not None and step_end is None:
            # End at next step heading, phase heading, or horizontal rule before next section
            if _STEP_HEADING_RE.match(line) or line.startswith("## "):
                step_end = i
                break

    if step_start is None:
        result["valid"] = False
        result["error"] = f"Step {step_num} not found in playbook"
        return result

    if step_end is None:
        step_end = len(lines)

    step_content = "".join(lines[step_start:step_end]).strip()
    result["content"] = step_content
    result["sections_included"].append(f"step-{step_num}")

    # --- Optionally include Universal Step Protocol ---
    if include_universal:
        universal_start = None
        universal_end = None
        for i, line in enumerate(lines):
            if _UNIVERSAL_HEADING in line:
                universal_start = i
                continue
            if universal_start is not None and universal_end is None:
                if line.strip() == "---":
                    universal_end = i
                    break

        if universal_start is not None:
            if universal_end is None:
                universal_end = len(lines)
            universal_content = "".join(lines[universal_start:universal_end]).strip()
            result["content"] = universal_content + "\n\n---\n\n" + result["content"]
            result["sections_included"].insert(0, "universal-protocol")
        else:
            result["warnings"].append("Universal Step Protocol section not found")

    # --- Optionally include Failure Recovery Reference ---
    if include_failure:
        failure_start = None
        failure_end = None
        for i, line in enumerate(lines):
            if _FAILURE_HEADING in line:
                failure_start = i
                continue
            if failure_start is not None and failure_end is None:
                # End at Team Management or Step-Type Quick Map
                if line.startswith("## ") and _FAILURE_HEADING not in line:
                    failure_end = i
                    break

        if failure_start is not None:
            if failure_end is None:
                failure_end = len(lines)
            failure_content = "".join(lines[failure_start:failure_end]).strip()
            result["content"] += "\n\n---\n\n" + failure_content
            result["sections_included"].append("failure-recovery")
        else:
            result["warnings"].append("Failure Recovery Reference section not found")

    result["content_lines"] = result["content"].count("\n") + 1
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract step guide from Orchestrator Playbook")
    parser.add_argument("--step", type=int, required=True, help="Step number to extract")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument("--include-universal", action="store_true",
                        help="Include Universal Step Protocol section")
    parser.add_argument("--include-failure-recovery", action="store_true",
                        help="Include Failure Recovery Reference section")
    args = parser.parse_args()

    playbook_path = os.path.join(args.project_dir, "ORCHESTRATOR-PLAYBOOK.md")
    result = extract_step_guide(
        playbook_path, args.step,
        include_universal=args.include_universal,
        include_failure=args.include_failure_recovery,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
