#!/usr/bin/env python3
"""Step Transition Validator — P1 deterministic pre-condition check.

Validates that advancing to the next step is safe:
  ST1: current_step matches expected
  ST2: All previous step outputs exist (L0 batch)
  ST3: Quality gates for current step all passed
  ST4: Team step completion check
  ST5: Review verdict check (if applicable)
  ST6: Translation file check (if applicable)

Usage:
    python3 scripts/validate_step_transition.py --step 3 --project-dir .

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# D-7 intentional duplication — must match _context_lib.py:SOT_FILENAMES
SOT_FILENAMES = ("state.yaml", "state.yml", "state.json")
MIN_OUTPUT_SIZE = 100


def _find_sot(project_dir):
    for fn in SOT_FILENAMES:
        p = os.path.join(project_dir, ".claude", fn)
        if os.path.exists(p):
            return p
    return None


def _read_sot(project_dir):
    sot = _find_sot(project_dir)
    if not sot:
        return None, "SOT file not found"
    try:
        import yaml
        with open(sot, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            wf = data.get("workflow", data)
            return wf, None
        return None, "SOT root is not a mapping"
    except Exception as e:
        return None, str(e)


def _check_file_exists(project_dir, rel_path):
    """Check if file exists and meets minimum size."""
    if not rel_path:
        return False, "empty path"
    full = os.path.join(project_dir, rel_path) if not os.path.isabs(rel_path) else rel_path
    if not os.path.exists(full):
        return False, f"file not found: {rel_path}"
    size = os.path.getsize(full)
    if size < MIN_OUTPUT_SIZE:
        return False, f"file too small: {size} bytes (min {MIN_OUTPUT_SIZE})"
    return True, None


def _check_quality_gate_logs(project_dir, step_num):
    """Check that quality gate logs exist for step."""
    warnings = []

    # L1: verification log
    verify_path = os.path.join(project_dir, "verification-logs", f"step-{step_num}-verify.md")
    if not os.path.exists(verify_path):
        warnings.append(f"QG1: verification log missing: verification-logs/step-{step_num}-verify.md")
    else:
        # Check for FAIL in verification log
        try:
            with open(verify_path, "r", encoding="utf-8") as f:
                content = f.read()
            if re.search(r'\bFAIL\b', content) and not re.search(r'overall.*PASS', content, re.IGNORECASE):
                warnings.append(f"QG1b: verification log contains FAIL without overall PASS")
        except Exception:
            pass

    # L1.5: pACS log
    pacs_path = os.path.join(project_dir, "pacs-logs", f"step-{step_num}-pacs.md")
    if not os.path.exists(pacs_path):
        warnings.append(f"QG2: pACS log missing: pacs-logs/step-{step_num}-pacs.md")
    else:
        # Check for RED zone
        try:
            with open(pacs_path, "r", encoding="utf-8") as f:
                content = f.read()
            score_match = re.search(r'pACS\s*=\s*(\d+)', content)
            if score_match:
                score = int(score_match.group(1))
                if score < 50:
                    warnings.append(f"QG2b: pACS score is {score} (RED zone < 50)")
        except Exception:
            pass

    return warnings


def _check_review_log(project_dir, step_num):
    """Check review log verdict if it exists."""
    review_path = os.path.join(project_dir, "review-logs", f"step-{step_num}-review.md")
    if not os.path.exists(review_path):
        return None  # No review required for this step
    try:
        with open(review_path, "r", encoding="utf-8") as f:
            content = f.read()
        verdict_match = re.search(r'Verdict\s*:\s*\*?\*?\s*(PASS|FAIL)', content, re.IGNORECASE)
        if verdict_match:
            return verdict_match.group(1).upper()
        return "UNKNOWN"
    except Exception:
        return "ERROR"


def validate_transition(project_dir, step_num):
    """Validate all pre-conditions for advancing past step_num."""
    result = {
        "valid": True,
        "step": step_num,
        "checks": {},
        "warnings": [],
        "blocking": [],
    }

    # Read SOT
    wf, err = _read_sot(project_dir)
    if err:
        result["valid"] = False
        result["blocking"].append(f"SOT_READ: {err}")
        return result

    # ST1: current_step matches
    cs = wf.get("current_step", 0)
    if cs != step_num:
        result["blocking"].append(f"ST1: current_step is {cs}, expected {step_num}")
        result["checks"]["ST1"] = "FAIL"
    else:
        result["checks"]["ST1"] = "PASS"

    # ST2: All previous outputs exist
    outputs = wf.get("outputs", {})
    st2_pass = True
    for prev in range(1, step_num):
        key = f"step-{prev}"
        if key not in outputs:
            # Skip human steps (4, 8, 18) which have no file output
            if prev in (4, 8, 18):
                continue
            result["blocking"].append(f"ST2: No output for {key}")
            st2_pass = False
        else:
            ok, err = _check_file_exists(project_dir, outputs[key])
            if not ok:
                result["blocking"].append(f"ST2: {key} output invalid: {err}")
                st2_pass = False
    result["checks"]["ST2"] = "PASS" if st2_pass else "FAIL"

    # ST3: Quality gates passed
    qg_warnings = _check_quality_gate_logs(project_dir, step_num)
    if qg_warnings:
        for w in qg_warnings:
            result["blocking"].append(w)
        result["checks"]["ST3"] = "FAIL"
    else:
        result["checks"]["ST3"] = "PASS"

    # ST4: Team completion check
    active_team = wf.get("active_team")
    if isinstance(active_team, dict) and active_team.get("status") != "all_completed":
        pending = active_team.get("tasks_pending", [])
        if pending:
            result["blocking"].append(f"ST4: active_team has pending tasks: {pending}")
            result["checks"]["ST4"] = "FAIL"
        else:
            result["checks"]["ST4"] = "PASS"
    else:
        result["checks"]["ST4"] = "PASS"

    # ST5: Review verdict
    verdict = _check_review_log(project_dir, step_num)
    if verdict is not None:
        if verdict == "FAIL":
            result["blocking"].append(f"ST5: Review verdict is FAIL")
            result["checks"]["ST5"] = "FAIL"
        elif verdict == "PASS":
            result["checks"]["ST5"] = "PASS"
        else:
            result["warnings"].append(f"ST5: Review verdict unclear: {verdict}")
            result["checks"]["ST5"] = "WARNING"
    else:
        result["checks"]["ST5"] = "N/A"

    # ST6: Translation check (look for step-N-ko in outputs)
    ko_key = f"step-{step_num}-ko"
    # Check if this step should have translation (by checking if ko key exists or will be expected)
    if ko_key in outputs:
        ok, err = _check_file_exists(project_dir, outputs[ko_key])
        if not ok:
            result["warnings"].append(f"ST6: Translation file invalid: {err}")
            result["checks"]["ST6"] = "WARNING"
        else:
            result["checks"]["ST6"] = "PASS"
    else:
        result["checks"]["ST6"] = "N/A"

    # Final verdict
    if result["blocking"]:
        result["valid"] = False

    return result


def main():
    parser = argparse.ArgumentParser(description="Step Transition Validator — P1")
    parser.add_argument("--step", type=int, required=True, help="Step number to validate transition for")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    args = parser.parse_args()

    result = validate_transition(args.project_dir, args.step)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
