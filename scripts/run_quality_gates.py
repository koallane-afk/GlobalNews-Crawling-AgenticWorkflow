#!/usr/bin/env python3
"""Quality Gate Sequencer — P1 deterministic gate ordering.

Enforces L0 → L1 → L1.5 → L2 order. Prevents skipping gates.
The Orchestrator calls this script instead of manually tracking gate results.

Usage:
    python3 scripts/run_quality_gates.py --step 3 --project-dir .
    python3 scripts/run_quality_gates.py --step 3 --project-dir . --check-review
    python3 scripts/run_quality_gates.py --step 3 --project-dir . --skip-review

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Constants — Step configuration
# ---------------------------------------------------------------------------

# Steps that require review (L2) — from workflow.md
REVIEW_STEPS = {1, 3, 5, 7, 16, 19, 20}

# Steps that are human-only (no quality gates)
HUMAN_STEPS = {4, 8, 18}

# Steps that require translation — from workflow.md
# D-7 cross-reference: must match ORCHESTRATOR-PLAYBOOK.md Step-Type Quick Map "Translation" column
TRANSLATION_STEPS = {1, 3, 5, 7, 16, 19, 20}

# Pre/post processing scripts per step
STEP_SCRIPTS = {
    1: {
        "pre": ["scripts/extract_site_urls.py"],
        "post": ["scripts/generate_sources_yaml_draft.py"],
    },
    3: {
        "pre": ["scripts/merge_recon_and_deps.py"],
        "post": [],
    },
    5: {
        "pre": ["scripts/filter_prd_architecture.py"],
        "post": ["scripts/validate_data_schema.py"],
    },
    6: {
        "pre": ["scripts/split_sites_by_group.py"],
        "post": ["scripts/validate_site_coverage.py"],
    },
    7: {
        "pre": ["scripts/filter_prd_analysis.py"],
        "post": [],
    },
    10: {
        "pre": ["scripts/extract_architecture_crawling.py"],
        "post": [],
    },
    11: {
        "pre": ["scripts/distribute_sites_to_teams.py"],
        "post": ["scripts/verify_adapter_coverage.py"],
    },
    13: {
        "pre": ["scripts/extract_pipeline_design_s1_s4.py"],
        "post": [],
    },
    14: {
        "pre": ["scripts/extract_pipeline_design_s5_s8.py"],
        "post": [],
    },
    16: {
        "pre": [],
        "post": ["scripts/calculate_success_metrics.py"],
    },
}


def _run_validator(cmd, project_dir):
    """Run a validation script and return parsed JSON result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_dir,
        )
        if result.stdout.strip():
            return json.loads(result.stdout.strip())
        return {"valid": False, "error": f"No output from {cmd[0]}", "stderr": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": f"Timeout running {cmd[0]}"}
    except json.JSONDecodeError:
        return {"valid": False, "error": f"Invalid JSON from {cmd[0]}"}
    except FileNotFoundError:
        return {"valid": False, "error": f"Script not found: {cmd[0]}"}


def check_quality_gates(project_dir, step_num, check_review=False):
    """Run quality gates in order: L0 → L1 → L1.5 → L2."""
    result = {
        "valid": True,
        "step": step_num,
        "gates": {},
        "blocking": [],
        "warnings": [],
        "scripts_status": {"pre": {}, "post": {}},
    }

    # Human steps have no quality gates
    if step_num in HUMAN_STEPS:
        result["gates"]["human_step"] = "SKIP"
        return result

    hooks_dir = os.path.join(project_dir, ".claude", "hooks", "scripts")

    # --- Pre-processing scripts check ---
    step_scripts = STEP_SCRIPTS.get(step_num, {"pre": [], "post": []})
    for script in step_scripts.get("pre", []):
        script_path = os.path.join(project_dir, script)
        result["scripts_status"]["pre"][script] = "EXISTS" if os.path.exists(script_path) else "MISSING"

    # --- L0: Anti-Skip Guard ---
    l0_cmd = [
        sys.executable,
        os.path.join(hooks_dir, "validate_pacs.py"),
        "--step", str(step_num),
        "--check-l0",
        "--project-dir", project_dir,
    ]
    l0_result = _run_validator(l0_cmd, project_dir)
    l0_valid = l0_result.get("l0_valid", l0_result.get("valid", False))
    result["gates"]["L0_anti_skip"] = "PASS" if l0_valid else "FAIL"
    if not l0_valid:
        l0_warnings = l0_result.get("l0_warnings", l0_result.get("warnings", []))
        result["blocking"].append(f"L0: Anti-Skip Guard failed: {l0_warnings}")
        result["valid"] = False
        return result  # Cannot proceed without L0

    # --- L1: Verification Gate ---
    l1_cmd = [
        sys.executable,
        os.path.join(hooks_dir, "validate_verification.py"),
        "--step", str(step_num),
        "--project-dir", project_dir,
    ]
    l1_result = _run_validator(l1_cmd, project_dir)
    l1_valid = l1_result.get("valid", False)
    result["gates"]["L1_verification"] = "PASS" if l1_valid else "FAIL"
    if not l1_valid:
        result["blocking"].append(f"L1: Verification Gate failed: {l1_result.get('warnings', [])}")
        result["valid"] = False
        return result  # Cannot proceed to L1.5 without L1

    # --- L1.5: pACS Self-Rating ---
    l15_cmd = [
        sys.executable,
        os.path.join(hooks_dir, "validate_pacs.py"),
        "--step", str(step_num),
        "--project-dir", project_dir,
    ]
    l15_result = _run_validator(l15_cmd, project_dir)
    l15_valid = l15_result.get("valid", False)
    result["gates"]["L1_5_pacs"] = "PASS" if l15_valid else "FAIL"
    if not l15_valid:
        result["blocking"].append(f"L1.5: pACS validation failed: {l15_result.get('warnings', [])}")
        result["valid"] = False
        return result  # Cannot proceed to L2 without L1.5

    # --- L2: Adversarial Review (optional) ---
    if check_review and step_num in REVIEW_STEPS:
        l2_cmd = [
            sys.executable,
            os.path.join(hooks_dir, "validate_review.py"),
            "--step", str(step_num),
            "--project-dir", project_dir,
            "--check-pacs-arithmetic",
        ]
        l2_result = _run_validator(l2_cmd, project_dir)
        l2_valid = l2_result.get("valid", False)
        verdict = l2_result.get("verdict", "UNKNOWN")
        result["gates"]["L2_review"] = f"{'PASS' if l2_valid and verdict == 'PASS' else 'FAIL'} (verdict={verdict})"
        if not l2_valid or verdict == "FAIL":
            result["blocking"].append(f"L2: Review validation failed: verdict={verdict}")
            result["valid"] = False
    elif step_num in REVIEW_STEPS:
        result["gates"]["L2_review"] = "PENDING"
        result["warnings"].append("L2: Review step — run with --check-review after review completion")
    else:
        result["gates"]["L2_review"] = "N/A"

    # --- Post-processing scripts check ---
    for script in step_scripts.get("post", []):
        script_path = os.path.join(project_dir, script)
        result["scripts_status"]["post"][script] = "EXISTS" if os.path.exists(script_path) else "MISSING"

    # --- Translation check (P1 structural validation, not just existence) ---
    if step_num in TRANSLATION_STEPS:
        ko_path = os.path.join(project_dir, "pacs-logs", f"step-{step_num}-translation-pacs.md")
        if not os.path.exists(ko_path):
            result["warnings"].append(f"Translation pACS log not found for step {step_num}")
            result["gates"]["translation_pacs"] = "MISSING"
        else:
            # Validate via P1 script if available
            trans_validator = os.path.join(hooks_dir, "validate_translation.py")
            if os.path.exists(trans_validator):
                trans_cmd = [
                    sys.executable, trans_validator,
                    "--step", str(step_num),
                    "--project-dir", project_dir,
                    "--check-pacs",
                ]
                trans_result = _run_validator(trans_cmd, project_dir)
                trans_valid = trans_result.get("valid", False)
                result["gates"]["translation_pacs"] = "PASS" if trans_valid else "FAIL"
                if not trans_valid:
                    result["warnings"].append(
                        f"Translation P1 validation failed: {trans_result.get('warnings', [])}"
                    )
            else:
                result["gates"]["translation_pacs"] = "EXISTS"

    return result


def main():
    parser = argparse.ArgumentParser(description="Quality Gate Sequencer — P1")
    parser.add_argument("--step", type=int, required=True, help="Step number")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument("--check-review", action="store_true", help="Include L2 review check")
    parser.add_argument("--skip-review", action="store_true", help="Skip L2 even for review steps")
    args = parser.parse_args()

    check_review = args.check_review and not args.skip_review
    result = check_quality_gates(args.project_dir, args.step, check_review)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
