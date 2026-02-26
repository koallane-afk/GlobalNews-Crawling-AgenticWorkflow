#!/usr/bin/env python3
"""Workflow Starter — Deterministic startup context generator.

Reads SOT + workflow.md to produce a structured startup report.
The Orchestrator (LLM) calls this ONCE at workflow start to know
exactly where it is and what to do next.

Usage:
    python3 scripts/workflow_starter.py --project-dir .
    python3 scripts/workflow_starter.py --project-dir . --autopilot

JSON output to stdout. Exit code 0 always (errors in JSON).
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SOT_FILENAMES = ("state.yaml", "state.yml", "state.json")
MIN_OUTPUT_SIZE = 100

# Phase boundaries (inclusive)
PHASES = {
    "Research":       (1, 4),
    "Planning":       (5, 8),
    "Implementation": (9, 20),
}

# Step heading in workflow.md: ### 1. ... or ### 2. (team) ...
# Group 1: step number, Group 2: optional type tag (human/team), Group 3: step name
_WF_STEP_RE = re.compile(r"^### (\d+)\.\s+(?:\((human|team)\)\s+)?(.+)$")

# Sub-fields within a step block
_FIELD_RES = {
    "agent":          re.compile(r"^\s*-\s+\*\*Agent\*\*:\s*(.+)$"),
    "team":           re.compile(r"^\s*-\s+\*\*Team\*\*:\s*(.+)$"),
    "pre_processing": re.compile(r"^\s*-\s+\*\*Pre-processing\*\*:\s*(.+)$"),
    "post_processing":re.compile(r"^\s*-\s+\*\*Post-processing\*\*:\s*(.+)$"),
    "output":         re.compile(r"^\s*-\s+\*\*Output\*\*:\s*(.+)$"),
    "review":         re.compile(r"^\s*-\s+\*\*Review\*\*:\s*(.+)$"),
    "translation":    re.compile(r"^\s*-\s+\*\*Translation\*\*:\s*(.+)$"),
}
_VERIFICATION_START_RE = re.compile(r"^\s*-\s+\*\*Verification\*\*:")
_VERIFICATION_ITEM_RE  = re.compile(r"^\s+-\s+\[[ x]\]\s+(.+)$")

# Playbook step heading
_PB_STEP_RE = re.compile(r"^### Step (\d+):")


# ---------------------------------------------------------------------------
# SOT helpers
# ---------------------------------------------------------------------------

def _find_sot(project_dir):
    for fn in SOT_FILENAMES:
        p = os.path.join(project_dir, ".claude", fn)
        if os.path.exists(p):
            return p
    return None


def _read_sot(project_dir):
    sot_path = _find_sot(project_dir)
    if not sot_path:
        return None, "SOT file not found"
    try:
        import yaml
        with open(sot_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            wf = data.get("workflow", data)
            return wf, None
        return None, "SOT root is not a mapping"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Workflow.md parser
# ---------------------------------------------------------------------------

def _parse_workflow_steps(workflow_path):
    """Parse workflow.md and return {step_num: {name, agent, output, ...}}."""
    if not os.path.exists(workflow_path):
        return {}

    with open(workflow_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    steps = {}
    current_step = None
    in_verification = False

    for line in lines:
        line_stripped = line.rstrip("\n")

        # New step heading?
        m = _WF_STEP_RE.match(line_stripped)
        if m:
            step_num = int(m.group(1))
            type_tag = m.group(2)  # "human", "team", or None
            step_name = m.group(3).strip()
            current_step = step_num
            steps[step_num] = {
                "name": step_name,
                "type_tag": type_tag,  # from heading: (human), (team), or None
                "agent": None,
                "team": None,
                "pre_processing": None,
                "post_processing": None,
                "output": None,
                "review": None,
                "translation": None,
                "verification": [],
            }
            in_verification = False
            continue

        if current_step is None:
            continue

        # Verification block?
        if _VERIFICATION_START_RE.match(line_stripped):
            in_verification = True
            continue

        if in_verification:
            vm = _VERIFICATION_ITEM_RE.match(line_stripped)
            if vm:
                steps[current_step]["verification"].append(vm.group(1))
                continue
            # Non-matching line after verification: end verification block
            if line_stripped.strip() and not line_stripped.startswith("  "):
                in_verification = False

        # Field extraction
        for field_name, field_re in _FIELD_RES.items():
            fm = field_re.match(line_stripped)
            if fm:
                val = fm.group(1).strip()
                # Strip all backticks from markdown inline code formatting
                val = val.replace("`", "")
                steps[current_step][field_name] = val
                break

    return steps


# ---------------------------------------------------------------------------
# Readiness checks
# ---------------------------------------------------------------------------

def _get_phase(step_num):
    for phase, (lo, hi) in PHASES.items():
        if lo <= step_num <= hi:
            return phase
    return "Unknown"


def _check_previous_outputs(sot_wf, project_dir, current_step):
    """Verify all prior step outputs exist on disk."""
    missing = []
    outputs = sot_wf.get("outputs", {})
    for key, path in outputs.items():
        # Skip non-step keys (e.g., step-N-ko)
        step_part = key.replace("step-", "")
        if not step_part.isdigit():
            continue
        full = os.path.join(project_dir, path)
        if not os.path.exists(full):
            missing.append({"step_key": key, "path": path, "reason": "file_not_found"})
        elif os.path.getsize(full) < MIN_OUTPUT_SIZE:
            missing.append({"step_key": key, "path": path, "reason": "too_small"})
    return missing


def _check_required_scripts(project_dir):
    """Verify essential orchestrator scripts exist."""
    required = [
        "scripts/sot_manager.py",
        "scripts/validate_step_transition.py",
        "scripts/run_quality_gates.py",
        "scripts/extract_orchestrator_step_guide.py",
    ]
    missing = []
    for s in required:
        if not os.path.exists(os.path.join(project_dir, s)):
            missing.append(s)
    return missing


def _check_playbook(project_dir):
    """Check ORCHESTRATOR-PLAYBOOK.md exists."""
    pb = os.path.join(project_dir, "ORCHESTRATOR-PLAYBOOK.md")
    return os.path.exists(pb)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_startup_context(project_dir, enable_autopilot=False):
    """Generate structured startup context JSON."""
    result = {
        "valid": True,
        "readiness": "ready",
        "blocking_reasons": [],
        "warnings": [],
        # SOT state
        "current_step": None,
        "total_steps": None,
        "status": None,
        "phase": None,
        # Current step details
        "step_details": {},
        # Execution context
        "autopilot": False,
        "previous_outputs": {},
        "next_actions": [],
    }

    # 1. Read SOT
    sot_wf, err = _read_sot(project_dir)
    if err:
        result["valid"] = False
        result["readiness"] = "blocked"
        result["blocking_reasons"].append(f"SOT error: {err}")
        return result

    current_step = sot_wf.get("current_step", 1)
    total_steps = sot_wf.get("total_steps", 20)
    status = sot_wf.get("status", "unknown")

    result["current_step"] = current_step
    result["total_steps"] = total_steps
    result["status"] = status
    result["phase"] = _get_phase(current_step)
    result["previous_outputs"] = sot_wf.get("outputs", {})

    # Autopilot state
    autopilot_cfg = sot_wf.get("autopilot", {})
    is_autopilot = autopilot_cfg.get("enabled", False) or enable_autopilot
    result["autopilot"] = is_autopilot

    # pACS state
    pacs = sot_wf.get("pacs", {})
    result["pacs_state"] = {
        "current_score": pacs.get("current_step_score"),
        "dimensions": pacs.get("dimensions", {}),
        "weak_dimension": pacs.get("weak_dimension"),
    }

    # 2. Check completed status
    if status == "completed":
        result["readiness"] = "completed"
        result["warnings"].append("Workflow already completed. All 20 steps done.")
        return result

    # 3. Check infrastructure
    missing_scripts = _check_required_scripts(project_dir)
    if missing_scripts:
        result["readiness"] = "blocked"
        result["blocking_reasons"].append(
            f"Missing scripts: {', '.join(missing_scripts)}"
        )

    if not _check_playbook(project_dir):
        result["readiness"] = "blocked"
        result["blocking_reasons"].append("ORCHESTRATOR-PLAYBOOK.md not found")

    # 4. Check previous outputs
    missing_outputs = _check_previous_outputs(sot_wf, project_dir, current_step)
    if missing_outputs:
        for mo in missing_outputs:
            result["warnings"].append(
                f"Prior output {mo['step_key']}: {mo['reason']} ({mo['path']})"
            )

    # 5. Parse workflow.md for current step details
    wf_path = os.path.join(project_dir, "prompt", "workflow.md")
    all_steps = _parse_workflow_steps(wf_path)

    if current_step in all_steps:
        step_info = all_steps[current_step]
        result["step_details"] = step_info

        # Determine step type from heading tag or field presence
        type_tag = step_info.get("type_tag")
        if type_tag == "team" or step_info.get("team"):
            step_type = "team"
        elif type_tag == "human":
            step_type = "human"
        else:
            step_type = "solo"
        result["step_type"] = step_type
    else:
        result["warnings"].append(
            f"Step {current_step} not found in workflow.md"
        )
        result["step_type"] = "unknown"

    # 6. Build next_actions checklist
    actions = []
    actions.append(f"READ SOT → confirm current_step == {current_step}")
    actions.append(f"Read Verification criteria from workflow.md Step {current_step}")

    step_info = result.get("step_details", {})
    if step_info.get("pre_processing"):
        actions.append(f"Run Pre-processing: {step_info['pre_processing']}")

    if result.get("step_type") == "team":
        actions.append(f"Create team: {step_info.get('team', 'N/A')}")
    elif step_info.get("agent"):
        actions.append(f"Spawn agent: {step_info['agent']}")

    if step_info.get("output"):
        actions.append(f"Save output to: {step_info['output']}")

    if step_info.get("post_processing"):
        actions.append(f"Run Post-processing: {step_info['post_processing']}")

    actions.append(f"Record output: sot_manager.py --record-output {current_step} <path>")
    actions.append(f"Quality Gates: L0 → L1 → L1.5 pACS")

    if step_info.get("review"):
        actions.append(f"L2 Review: {step_info['review']}")

    if step_info.get("translation"):
        actions.append(f"Translation: {step_info['translation']}")

    actions.append(f"Validate transition: validate_step_transition.py --step {current_step}")
    actions.append(f"Advance: sot_manager.py --advance-step {current_step}")

    result["next_actions"] = actions

    # 7. Summary message
    phase = result["phase"]
    step_name = step_info.get("name", f"Step {current_step}")
    result["summary"] = (
        f"[WORKFLOW START] Step {current_step}/{total_steps} — "
        f"{phase} Phase — {step_name}"
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="Workflow Starter")
    parser.add_argument("--project-dir", required=True, help="Project root")
    parser.add_argument("--autopilot", action="store_true",
                        help="Enable autopilot mode")
    args = parser.parse_args()

    result = generate_startup_context(args.project_dir, args.autopilot)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()  # trailing newline
    sys.exit(0)


if __name__ == "__main__":
    main()
