#!/usr/bin/env python3
"""Team State Validator — P1 deterministic team lifecycle check.

Verifies team state consistency in SOT during team steps.
Used during Steps 2, 6, 10, 11, 13, 14 to prevent team state hallucination.

Usage:
    python3 scripts/validate_team_state.py --project-dir .
    python3 scripts/validate_team_state.py --project-dir . --check-dissolution

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# D-7 intentional duplication — must match _context_lib.py:SOT_FILENAMES
SOT_FILENAMES = ("state.yaml", "state.yml", "state.json")
VALID_TEAM_STATUSES = {"partial", "all_completed"}


def _read_sot(project_dir):
    """Read SOT and extract workflow dict."""
    for fn in SOT_FILENAMES:
        p = os.path.join(project_dir, ".claude", fn)
        if os.path.exists(p):
            try:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    wf = data.get("workflow", data)
                    return wf, None
            except Exception as e:
                return None, str(e)
    return None, "SOT file not found"


def validate_team(project_dir, check_dissolution=False):
    """Validate active_team state consistency."""
    result = {
        "valid": True,
        "checks": {},
        "warnings": [],
    }

    wf, err = _read_sot(project_dir)
    if err:
        result["valid"] = False
        result["warnings"].append(f"SOT: {err}")
        return result

    active_team = wf.get("active_team")
    if not isinstance(active_team, dict):
        result["checks"]["TS0"] = "N/A"
        result["warnings"].append("TS0: No active_team in SOT (team step may not have started)")
        return result

    # TS1: name exists and is non-empty
    name = active_team.get("name")
    if not name or not isinstance(name, str):
        result["valid"] = False
        result["checks"]["TS1"] = "FAIL"
        result["warnings"].append("TS1: active_team.name is missing or empty")
    else:
        result["checks"]["TS1"] = "PASS"

    # TS2: tasks_pending + tasks_completed == all tasks
    tc = active_team.get("tasks_completed", [])
    tp = active_team.get("tasks_pending", [])
    if not isinstance(tc, list):
        tc = []
    if not isinstance(tp, list):
        tp = []

    all_tasks = set(tc) | set(tp)
    # Check for overlap
    overlap = set(tc) & set(tp)
    if overlap:
        result["valid"] = False
        result["checks"]["TS2"] = "FAIL"
        result["warnings"].append(f"TS2: Tasks in both completed and pending: {list(overlap)}")
    else:
        result["checks"]["TS2"] = "PASS"

    result["tasks_completed"] = tc
    result["tasks_pending"] = tp
    result["total_tasks"] = len(all_tasks)

    # TS3: completed_summaries keys ⊆ tasks_completed
    cs = active_team.get("completed_summaries", {})
    if isinstance(cs, dict):
        summary_keys = set(cs.keys())
        extra_keys = summary_keys - set(tc)
        if extra_keys:
            result["valid"] = False
            result["checks"]["TS3"] = "FAIL"
            result["warnings"].append(f"TS3: Summaries for non-completed tasks: {list(extra_keys)}")
        else:
            result["checks"]["TS3"] = "PASS"

        # Check that each completed task has a summary
        missing_summaries = set(tc) - summary_keys
        if missing_summaries:
            result["warnings"].append(f"TS3b: Completed tasks without summaries: {list(missing_summaries)}")
            result["checks"]["TS3b"] = "WARNING"
    else:
        result["checks"]["TS3"] = "N/A"

    # TS4: Status consistency
    status = active_team.get("status", "unknown")
    if status not in VALID_TEAM_STATUSES:
        result["valid"] = False
        result["checks"]["TS4"] = "FAIL"
        result["warnings"].append(f"TS4: Invalid status: {status}")
    elif status == "all_completed" and tp:
        result["valid"] = False
        result["checks"]["TS4"] = "FAIL"
        result["warnings"].append(f"TS4: Status is 'all_completed' but {len(tp)} tasks still pending")
    elif status == "partial" and not tp:
        result["warnings"].append("TS4b: Status is 'partial' but no tasks pending — should be 'all_completed'")
        result["checks"]["TS4"] = "WARNING"
    else:
        result["checks"]["TS4"] = "PASS"

    # TS5: Dissolution check (completed_teams history)
    if check_dissolution:
        completed_teams = wf.get("completed_teams", [])
        if isinstance(completed_teams, list):
            result["completed_teams_count"] = len(completed_teams)
            # Check that dissolved teams have all tasks completed
            for i, team in enumerate(completed_teams):
                if isinstance(team, dict):
                    t_status = team.get("status")
                    if t_status != "all_completed":
                        result["warnings"].append(
                            f"TS5: completed_teams[{i}] ('{team.get('name')}') status is '{t_status}', not 'all_completed'"
                        )
                        result["checks"]["TS5"] = "WARNING"
            if "TS5" not in result["checks"]:
                result["checks"]["TS5"] = "PASS"
        else:
            result["checks"]["TS5"] = "N/A"

    result["team_name"] = name
    result["team_status"] = status

    return result


def main():
    parser = argparse.ArgumentParser(description="Team State Validator — P1")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument("--check-dissolution", action="store_true", help="Check completed_teams history")
    args = parser.parse_args()

    result = validate_team(args.project_dir, args.check_dissolution)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
