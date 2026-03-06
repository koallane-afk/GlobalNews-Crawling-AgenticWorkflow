"""Unit tests for autopilot structural reinforcement — ST7, HQ1/HQ2/HQ3, S6, DL1-DL6.

Tests cover:
- ST7: Decision log check in validate_step_transition.py
- HQ1/HQ2/HQ3: Human quality gates in run_quality_gates.py
- S6/S6b: HUMAN_STEPS_SET validation in _context_lib.py validate_sot_schema()
- D-7: HUMAN_STEPS constant consistency across 4 files
- DL1-DL6: Decision log P1 validation in _context_lib.py validate_decision_log()
"""

import importlib.util
import json
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
HOOKS_DIR = os.path.join(PROJECT_ROOT, ".claude", "hooks", "scripts")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def _import_script(name, directory=SCRIPTS_DIR):
    """Import a script module by name from a given directory."""
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(directory, f"{name}.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sot_mod():
    return _import_script("sot_manager")


@pytest.fixture
def transition_mod():
    return _import_script("validate_step_transition")


@pytest.fixture
def gates_mod():
    return _import_script("run_quality_gates")


@pytest.fixture
def context_lib():
    return _import_script("_context_lib", HOOKS_DIR)


@pytest.fixture
def tmp_project(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path


@pytest.fixture
def tmp_project_with_sot(tmp_project, sot_mod):
    result = sot_mod.cmd_init(str(tmp_project), "Test Workflow", 20)
    assert result["valid"]
    return tmp_project


def _enable_autopilot_at_step(sot_mod, pd, step_num):
    """Enable autopilot and set current_step to step_num."""
    import yaml
    sot_mod.cmd_set_autopilot(pd, "true")
    sot_path = sot_mod._sot_path(pd)
    with open(sot_path, "r") as f:
        data = yaml.safe_load(f)
    data["workflow"]["current_step"] = step_num
    with open(sot_path, "w") as f:
        yaml.dump(data, f)


def _create_decision_log(pd, step_num, size=200, template=True):
    """Create a decision log file.

    If template=True, creates a properly formatted decision log matching
    the autopilot-decision-template.md structure. If False, creates raw text.
    """
    log_dir = os.path.join(pd, "autopilot-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"step-{step_num}-decision.md")
    if template:
        content = (
            f"# Decision Log — Step {step_num}\n\n"
            f"- **Step**: {step_num}\n"
            f"- **Checkpoint Type**: (human) — Test checkpoint\n"
            f"- **Decision**: Proceed with quality-maximizing defaults per Autopilot mode\n"
            f"- **Rationale**: Absolute criterion 1 requires quality maximization with full coverage "
            f"of prior step-{step_num - 1} verification gates and L0 Anti-Skip Guard evidence\n"
            f"- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        # Pad to minimum size if needed
        if len(content) < size:
            content += "\n" + "x" * (size - len(content))
        with open(log_path, "w") as f:
            f.write(content)
    else:
        with open(log_path, "w") as f:
            f.write("# Decision Log\n" + "x" * size)


def _create_output(pd, path, size=200):
    """Create a dummy output file."""
    full = os.path.join(pd, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write("# Output\n" + "x" * size)


def _create_quality_logs(pd, step_num):
    """Create dummy verification + pACS logs for a step (HQ4 support)."""
    for subdir, suffix in [("verification-logs", "verify"), ("pacs-logs", "pacs")]:
        dir_path = os.path.join(pd, subdir)
        os.makedirs(dir_path, exist_ok=True)
        log_path = os.path.join(dir_path, f"step-{step_num}-{suffix}.md")
        with open(log_path, "w") as f:
            f.write(f"# {suffix.title()} — Step {step_num}\n" + "x" * 200)


# ============================================================================
# D-7: HUMAN_STEPS constant consistency
# ============================================================================

class TestHumanStepsConsistency:
    """Verify HUMAN_STEPS is identical across all 4 files (D-7)."""

    def test_d7_human_steps_all_match(self, sot_mod, transition_mod, gates_mod, context_lib):
        expected = frozenset({4, 8, 18})
        assert sot_mod.HUMAN_STEPS == expected, f"sot_manager: {sot_mod.HUMAN_STEPS}"
        assert transition_mod.HUMAN_STEPS == expected, f"validate_step_transition: {transition_mod.HUMAN_STEPS}"
        assert gates_mod.HUMAN_STEPS == expected, f"run_quality_gates: {gates_mod.HUMAN_STEPS}"
        assert context_lib.HUMAN_STEPS_SET == expected, f"_context_lib: {context_lib.HUMAN_STEPS_SET}"

    def test_d7_all_frozenset(self, sot_mod, transition_mod, gates_mod, context_lib):
        assert isinstance(sot_mod.HUMAN_STEPS, frozenset)
        assert isinstance(transition_mod.HUMAN_STEPS, frozenset)
        assert isinstance(gates_mod.HUMAN_STEPS, frozenset)
        assert isinstance(context_lib.HUMAN_STEPS_SET, frozenset)


# ============================================================================
# ST7: Decision log check in validate_step_transition.py
# ============================================================================

class TestST7DecisionLog:
    """Tests for ST7 blocking check in validate_transition."""

    def test_st7_pass_when_log_exists(self, transition_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        result = transition_mod.validate_transition(pd, 8)
        assert result["checks"]["ST7"] == "PASS"

    def test_st7_fail_when_log_missing(self, transition_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        # No decision log created
        result = transition_mod.validate_transition(pd, 8)
        assert result["checks"]["ST7"] == "FAIL"
        assert any("ST7" in b for b in result["blocking"])

    def test_st7_na_when_manual_mode(self, transition_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        # Autopilot is off (default)
        import yaml
        sot_path = sot_mod._sot_path(pd)
        with open(sot_path, "r") as f:
            data = yaml.safe_load(f)
        data["workflow"]["current_step"] = 8
        with open(sot_path, "w") as f:
            yaml.dump(data, f)
        result = transition_mod.validate_transition(pd, 8)
        assert result["checks"]["ST7"] == "N/A"

    def test_st7_na_for_non_human_step(self, transition_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 5)
        result = transition_mod.validate_transition(pd, 5)
        assert result["checks"]["ST7"] == "N/A"


# ============================================================================
# HQ1/HQ2/HQ3: Human quality gates in run_quality_gates.py
# ============================================================================

class TestHumanQualityGates:
    """Tests for HQ1/HQ2/HQ3 in check_quality_gates."""

    def test_auto_detect_runs_hq_when_autopilot_on(self, gates_mod, sot_mod, tmp_project_with_sot):
        """Auto-detection: autopilot ON → HQ gates run (no --check-autopilot needed)."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        # No decision log → HQ1 should FAIL (proving HQ gates DID run)
        result = gates_mod.check_quality_gates(pd, 8)
        assert "HQ1_decision_log" in result["gates"]
        assert result["gates"]["HQ1_decision_log"] == "FAIL"

    def test_hq_all_pass(self, gates_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        # Create decision log (template format)
        _create_decision_log(pd, 8)
        # Add to auto_approved
        sot_mod.cmd_add_auto_approved(pd, 8)
        # Create previous step output and record it
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        # Create quality gate logs for step 7 (HQ4 evidence)
        _create_quality_logs(pd, 7)
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["valid"] is True
        assert result["gates"]["HQ1_decision_log"] == "PASS"
        assert result["gates"]["HQ2_auto_approved"] == "PASS"
        assert result["gates"]["HQ3_prev_output"] == "PASS"
        assert result["gates"]["HQ4_prev_quality_evidence"] == "PASS"

    def test_hq1_fail_missing_log(self, gates_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ1_decision_log"] == "FAIL"
        assert result["valid"] is False

    def test_hq1_fail_too_small(self, gates_mod, sot_mod, tmp_project_with_sot):
        """F5: HQ1 threshold is 100 bytes (aligned with MIN_OUTPUT_SIZE)."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8, size=10, template=False)  # < 100 bytes
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ1_decision_log"] == "FAIL"

    def test_hq2_fail_not_approved(self, gates_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        # Don't add to auto_approved
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ2_auto_approved"] == "FAIL"

    def test_hq3_fail_no_prev_output(self, gates_mod, sot_mod, tmp_project_with_sot):
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        # No step-7 output recorded
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ3_prev_output"] == "FAIL"

    def test_hq_skip_when_autopilot_off(self, gates_mod, sot_mod, tmp_project_with_sot):
        """Autopilot OFF → human steps get SKIP regardless of flag."""
        pd = str(tmp_project_with_sot)
        # Autopilot is off by default
        import yaml
        sot_path = sot_mod._sot_path(pd)
        with open(sot_path, "r") as f:
            data = yaml.safe_load(f)
        data["workflow"]["current_step"] = 8
        with open(sot_path, "w") as f:
            yaml.dump(data, f)
        result = gates_mod.check_quality_gates(pd, 8)
        assert "human_step" in result["gates"]
        assert result["gates"]["human_step"] == "SKIP"

    def test_hq_saves_audit_log(self, gates_mod, sot_mod, tmp_project_with_sot):
        """F4: HQ gate results are auto-saved to autopilot-logs/step-N-hq-gates.json."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        _create_quality_logs(pd, 7)
        gates_mod.check_quality_gates(pd, 8)
        log_path = os.path.join(pd, "autopilot-logs", "step-8-hq-gates.json")
        assert os.path.exists(log_path)
        with open(log_path, "r") as f:
            log_data = json.load(f)
        assert log_data["step"] == 8
        assert log_data["valid"] is True
        assert "HQ1_decision_log" in log_data["gates"]


# ============================================================================
# S6/S6b: validate_sot_schema in _context_lib.py
# ============================================================================

class TestS6HumanStepsValidation:
    """Tests for S6 HUMAN_STEPS_SET check in validate_sot_schema."""

    def test_s6_valid_human_steps(self, context_lib):
        ap_state = {
            "enabled": True,
            "current_step": 20,
            "auto_approved_steps": [4, 8, 18],
        }
        warnings = context_lib.validate_sot_schema(ap_state)
        s6_warnings = [w for w in warnings if "non-human" in w]
        assert len(s6_warnings) == 0

    def test_s6_non_human_step_warned(self, context_lib):
        ap_state = {
            "enabled": True,
            "current_step": 20,
            "auto_approved_steps": [5],
        }
        warnings = context_lib.validate_sot_schema(ap_state)
        assert any("non-human step" in w for w in warnings)

    def test_s6_mixed_valid_invalid(self, context_lib):
        ap_state = {
            "enabled": True,
            "current_step": 20,
            "auto_approved_steps": [4, 5, 8],
        }
        warnings = context_lib.validate_sot_schema(ap_state)
        non_human = [w for w in warnings if "non-human" in w]
        assert len(non_human) == 1
        assert "5" in non_human[0]

    def test_s6b_enabled_bool_valid(self, context_lib):
        ap_state = {"enabled": True, "auto_approved_steps": []}
        warnings = context_lib.validate_sot_schema(ap_state)
        s6b_warnings = [w for w in warnings if "autopilot.enabled" in w]
        assert len(s6b_warnings) == 0

    def test_s6b_enabled_non_bool_warned(self, context_lib):
        ap_state = {"enabled": "true", "auto_approved_steps": []}
        warnings = context_lib.validate_sot_schema(ap_state)
        assert any("autopilot.enabled" in w for w in warnings)

    def test_s6_empty_auto_approved_valid(self, context_lib):
        ap_state = {"enabled": True, "auto_approved_steps": []}
        warnings = context_lib.validate_sot_schema(ap_state)
        s6_warnings = [w for w in warnings if "auto_approved" in w]
        assert len(s6_warnings) == 0


# ============================================================================
# DL1-DL6: Decision Log P1 Validation in _context_lib.py
# ============================================================================

class TestDecisionLogValidation:
    """Tests for validate_decision_log() P1 checks (DL1-DL6)."""

    def test_dl1_fail_missing_file(self, context_lib, tmp_path):
        """DL1: Non-existent decision log → FAIL."""
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL1"] == "FAIL"
        assert any("DL1" in w for w in result["warnings"])

    def test_dl1_pass_existing_file(self, context_lib, tmp_path):
        """DL1: Existing decision log → PASS (DL1 only)."""
        _create_decision_log(str(tmp_path), 8)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL1"] == "PASS"

    def test_dl2_fail_too_small(self, context_lib, tmp_path):
        """DL2: Decision log < 100 bytes → FAIL."""
        _create_decision_log(str(tmp_path), 8, size=10, template=False)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL2"] == "FAIL"

    def test_dl2_pass_adequate_size(self, context_lib, tmp_path):
        """DL2: Decision log >= 100 bytes → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL2"] == "PASS"

    def test_dl3_fail_missing_sections(self, context_lib, tmp_path):
        """DL3: Raw text without required sections → FAIL."""
        _create_decision_log(str(tmp_path), 8, size=200, template=False)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL3"] == "FAIL"
        assert any("DL3" in w and "Missing" in w for w in result["warnings"])

    def test_dl3_pass_all_sections_present(self, context_lib, tmp_path):
        """DL3: Template-formatted log with all sections → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL3"] == "PASS"

    def test_dl4_fail_step_mismatch(self, context_lib, tmp_path):
        """DL4: Log says step 4 but we validate step 8 → FAIL."""
        _create_decision_log(str(tmp_path), 4, size=200, template=True)
        # Rename the file to step-8 so DL1 passes, but content says step 4
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.rename(
            os.path.join(log_dir, "step-4-decision.md"),
            os.path.join(log_dir, "step-8-decision.md"),
        )
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL4"] == "FAIL"
        assert any("DL4" in w and "mismatch" in w for w in result["warnings"])

    def test_dl4_pass_step_matches(self, context_lib, tmp_path):
        """DL4: Log says step 8 and we validate step 8 → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL4"] == "PASS"

    def test_dl5_fail_rationale_too_short(self, context_lib, tmp_path):
        """DL5: Rationale field with < 10 chars → FAIL."""
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.makedirs(log_dir, exist_ok=True)
        content = (
            "# Decision Log — Step 8\n\n"
            "- **Step**: 8\n"
            "- **Checkpoint Type**: (human) — Test\n"
            "- **Decision**: Proceed with quality-maximizing defaults for this step\n"
            "- **Rationale**: OK\n"  # Only 2 chars — too short
            "- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        content += "\n" + "x" * (200 - len(content))
        with open(os.path.join(log_dir, "step-8-decision.md"), "w") as f:
            f.write(content)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL5"] == "FAIL"

    def test_dl5_pass_rationale_adequate(self, context_lib, tmp_path):
        """DL5: Rationale with >= 10 chars → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL5"] == "PASS"

    def test_dl6_fail_decision_too_short(self, context_lib, tmp_path):
        """DL6: Decision field with < 5 chars → FAIL."""
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.makedirs(log_dir, exist_ok=True)
        content = (
            "# Decision Log — Step 8\n\n"
            "- **Step**: 8\n"
            "- **Checkpoint Type**: (human) — Test\n"
            "- **Decision**: OK\n"  # Only 2 chars — too short
            "- **Rationale**: Absolute criterion 1 — quality maximization requires full coverage\n"
            "- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        content += "\n" + "x" * (200 - len(content))
        with open(os.path.join(log_dir, "step-8-decision.md"), "w") as f:
            f.write(content)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is False
        assert result["checks"]["DL6"] == "FAIL"

    def test_dl6_pass_decision_adequate(self, context_lib, tmp_path):
        """DL6: Decision with >= 5 chars → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL6"] == "PASS"

    def test_all_pass_template_log(self, context_lib, tmp_path):
        """All DL1-DL8 pass with a properly formatted template log."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["valid"] is True
        for check_id in ("DL1", "DL2", "DL3", "DL4", "DL5", "DL6"):
            assert result["checks"][check_id] == "PASS", f"{check_id} not PASS"
        # DL7/DL8 are WARNING-level — template should pass both
        assert result["checks"]["DL7"] == "PASS", "DL7 not PASS"
        assert result["checks"]["DL8"] == "PASS", "DL8 not PASS"

    def test_early_return_on_dl1_fail(self, context_lib, tmp_path):
        """DL1 failure returns immediately — no DL2-DL6 checks attempted."""
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert "DL1" in result["checks"]
        assert "DL2" not in result["checks"]

    def test_early_return_on_dl2_fail(self, context_lib, tmp_path):
        """DL2 failure returns immediately — no DL3-DL6 checks attempted."""
        _create_decision_log(str(tmp_path), 8, size=10, template=False)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL1"] == "PASS"
        assert result["checks"]["DL2"] == "FAIL"
        assert "DL3" not in result["checks"]


# ============================================================================
# DL7/DL8: Decision Log Content Quality Validation (WARNING-level)
# ============================================================================

class TestDecisionLogContentQuality:
    """Tests for DL7/DL8 content quality checks (WARNING, non-blocking)."""

    def test_dl7_pass_with_evidence_reference(self, context_lib, tmp_path):
        """DL7: Rationale with 'absolute criterion' reference → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL7"] == "PASS"
        assert result["valid"] is True  # DL7 WARNING doesn't affect valid

    def test_dl7_warning_no_evidence(self, context_lib, tmp_path):
        """DL7: Rationale without evidence reference → WARNING (not FAIL)."""
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.makedirs(log_dir, exist_ok=True)
        content = (
            "# Decision Log — Step 8\n\n"
            "- **Step**: 8\n"
            "- **Checkpoint Type**: (human) — Test checkpoint\n"
            "- **Decision**: Proceed with the default approach for this review checkpoint\n"
            "- **Rationale**: Everything looks good and the output is satisfactory enough to move forward now\n"
            "- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        content += "\n" + "x" * (200 - len(content))
        with open(os.path.join(log_dir, "step-8-decision.md"), "w") as f:
            f.write(content)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL7"] == "WARNING"
        assert result["valid"] is True  # WARNING doesn't block

    def test_dl8_pass_sufficient_words(self, context_lib, tmp_path):
        """DL8: Rationale with >= 15 words → PASS."""
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL8"] == "PASS"

    def test_dl8_warning_too_few_words(self, context_lib, tmp_path):
        """DL8: Rationale with < 15 words → WARNING (not FAIL)."""
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.makedirs(log_dir, exist_ok=True)
        content = (
            "# Decision Log — Step 8\n\n"
            "- **Step**: 8\n"
            "- **Checkpoint Type**: (human) — Test\n"
            "- **Decision**: Proceed with quality-maximizing defaults per Autopilot mode\n"
            "- **Rationale**: Quality maximization OK\n"  # 3 words — too few
            "- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        content += "\n" + "x" * (200 - len(content))
        with open(os.path.join(log_dir, "step-8-decision.md"), "w") as f:
            f.write(content)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL8"] == "WARNING"
        assert result["valid"] is True  # WARNING doesn't block

    def test_dl7_dl8_dont_affect_valid(self, context_lib, tmp_path):
        """DL7/DL8 WARNINGs never set valid=False."""
        log_dir = os.path.join(str(tmp_path), "autopilot-logs")
        os.makedirs(log_dir, exist_ok=True)
        content = (
            "# Decision Log — Step 8\n\n"
            "- **Step**: 8\n"
            "- **Checkpoint Type**: (human) — Test\n"
            "- **Decision**: Proceed with defaults for this checkpoint\n"
            "- **Rationale**: Looks fine\n"  # No evidence, < 15 words
            "- **Timestamp**: 2026-02-28 12:00:00\n"
        )
        content += "\n" + "x" * (200 - len(content))
        with open(os.path.join(log_dir, "step-8-decision.md"), "w") as f:
            f.write(content)
        result = context_lib.validate_decision_log(str(tmp_path), 8)
        assert result["checks"]["DL7"] == "WARNING"
        assert result["checks"]["DL8"] == "WARNING"
        # DL5 checks char count (10+), not word count — "Looks fine" is 10 chars
        assert result["valid"] is True


# ============================================================================
# ST4b: Team completion cross-validation
# ============================================================================

class TestST4CrossValidation:
    """Tests for ST4b — all_completed with non-empty tasks_pending."""

    def test_st4_fail_completed_but_pending(self, transition_mod, sot_mod, tmp_project_with_sot):
        """ST4: status=all_completed but tasks_pending non-empty → FAIL."""
        import yaml
        pd = str(tmp_project_with_sot)
        sot_path = sot_mod._sot_path(pd)
        with open(sot_path, "r") as f:
            data = yaml.safe_load(f)
        data["workflow"]["current_step"] = 10
        data["workflow"]["active_team"] = {
            "name": "test-team",
            "status": "all_completed",
            "tasks_completed": ["task-1"],
            "tasks_pending": ["task-2"],  # Inconsistent!
            "completed_summaries": {},
        }
        with open(sot_path, "w") as f:
            yaml.dump(data, f)
        result = transition_mod.validate_transition(pd, 10)
        assert result["checks"]["ST4"] == "FAIL"
        assert any("all_completed" in b and "non-empty" in b for b in result["blocking"])

    def test_st4_pass_completed_and_empty_pending(self, transition_mod, sot_mod, tmp_project_with_sot):
        """ST4: status=all_completed with empty tasks_pending → PASS."""
        import yaml
        pd = str(tmp_project_with_sot)
        sot_path = sot_mod._sot_path(pd)
        with open(sot_path, "r") as f:
            data = yaml.safe_load(f)
        data["workflow"]["current_step"] = 10
        data["workflow"]["active_team"] = {
            "name": "test-team",
            "status": "all_completed",
            "tasks_completed": ["task-1", "task-2"],
            "tasks_pending": [],
            "completed_summaries": {},
        }
        with open(sot_path, "w") as f:
            yaml.dump(data, f)
        result = transition_mod.validate_transition(pd, 10)
        assert result["checks"]["ST4"] == "PASS"


# ============================================================================
# HQ4: Previous Step Quality Gate Evidence
# ============================================================================

class TestHQ4QualityEvidence:
    """Tests for HQ4 — previous non-human step quality gate evidence."""

    def test_hq4_pass_both_logs_exist(self, gates_mod, sot_mod, tmp_project_with_sot):
        """HQ4: Both verification and pACS logs exist → PASS."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        _create_quality_logs(pd, 7)
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ4_prev_quality_evidence"] == "PASS"

    def test_hq4_fail_partial_logs(self, gates_mod, sot_mod, tmp_project_with_sot):
        """HQ4: Only verification log (no pACS) → FAIL (partial gate execution)."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        # Only create verification log, not pACS
        vdir = os.path.join(pd, "verification-logs")
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, "step-7-verify.md"), "w") as f:
            f.write("# Verify\n" + "x" * 200)
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ4_prev_quality_evidence"] == "FAIL"

    def test_hq4_warning_no_logs_at_all(self, gates_mod, sot_mod, tmp_project_with_sot):
        """HQ4: No logs at all → WARNING (early workflow, never ran gates)."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        _create_decision_log(pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        _create_output(pd, "planning/step-7.md")
        sot_mod.cmd_record_output(pd, 7, "planning/step-7.md")
        # No quality logs created
        result = gates_mod.check_quality_gates(pd, 8)
        assert result["gates"]["HQ4_prev_quality_evidence"] == "WARNING"

    def test_hq4_na_step4_no_prior_non_human(self, gates_mod, sot_mod, tmp_project_with_sot):
        """HQ4: Step 4 — prior non-human step is 3. Walk-back finds it."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 4)
        _create_decision_log(pd, 4)
        sot_mod.cmd_add_auto_approved(pd, 4)
        _create_output(pd, "research/step-3.md")
        sot_mod.cmd_record_output(pd, 3, "research/step-3.md")
        _create_quality_logs(pd, 3)
        result = gates_mod.check_quality_gates(pd, 4)
        assert result["gates"]["HQ4_prev_quality_evidence"] == "PASS"


# ============================================================================
# L0d Blocking Mode
# ============================================================================

@pytest.fixture
def pacs_mod():
    return _import_script("validate_pacs", HOOKS_DIR)


class TestL0dBlockingMode:
    """Tests for L0d blocking mode via output-structure.yaml blocking_steps."""

    def test_l0d_blocking_not_triggered_default(self, pacs_mod, tmp_path):
        """L0d: Default blocking_steps=[] → L0d failure stays WARNING."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        with open(config_dir / "output-structure.yaml", "w") as f:
            f.write("blocking_steps: []\nsteps:\n  1:\n    checks:\n      - type: heading\n        pattern: '## NONEXISTENT'\n        description: test\n")
        result = pacs_mod._load_l0d_blocking_steps(str(tmp_path))
        assert result == set()

    def test_l0d_blocking_steps_loaded(self, pacs_mod, tmp_path):
        """L0d: blocking_steps=[1, 5] loads correctly."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        with open(config_dir / "output-structure.yaml", "w") as f:
            f.write("blocking_steps: [1, 5]\nsteps: {}\n")
        result = pacs_mod._load_l0d_blocking_steps(str(tmp_path))
        assert result == {1, 5}

    def test_l0d_blocking_missing_config(self, pacs_mod, tmp_path):
        """L0d: Missing config file → empty set (backward compatible)."""
        result = pacs_mod._load_l0d_blocking_steps(str(tmp_path))
        assert result == set()


# ============================================================================
# Change 4: Autopilot Loop Stall Detection
# ============================================================================

class TestAutopilotStallDetection:
    """Tests for check_autopilot_progress() stall detection."""

    def test_no_warning_below_threshold(self, context_lib, tmp_project_with_sot, sot_mod):
        """Stall: 1 cycle on step 5 → no warning."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 5)
        result = context_lib.check_autopilot_progress(pd)
        assert result is None

    def test_warning_at_threshold(self, context_lib, tmp_project_with_sot, sot_mod):
        """Stall: 20 cycles on same step → warning returned."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 5)
        # Simulate 20 cycles by writing tracker directly
        import json
        logs_dir = os.path.join(pd, "autopilot-logs")
        os.makedirs(logs_dir, exist_ok=True)
        tracker_path = os.path.join(logs_dir, ".progress-tracker")
        with open(tracker_path, "w") as f:
            json.dump({"step": 5, "cycles": 19}, f)
        result = context_lib.check_autopilot_progress(pd)
        assert result is not None
        assert "Stall" in result
        assert "Step 5" in result

    def test_reset_on_step_advance(self, context_lib, tmp_project_with_sot, sot_mod):
        """Stall: Step advances → cycles reset to 1."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 6)
        import json
        logs_dir = os.path.join(pd, "autopilot-logs")
        os.makedirs(logs_dir, exist_ok=True)
        tracker_path = os.path.join(logs_dir, ".progress-tracker")
        # Was stuck at step 5 with 19 cycles
        with open(tracker_path, "w") as f:
            json.dump({"step": 5, "cycles": 19}, f)
        # Now current_step is 6 — should reset
        result = context_lib.check_autopilot_progress(pd)
        assert result is None
        # Verify tracker was reset
        with open(tracker_path, "r") as f:
            tracker = json.load(f)
        assert tracker["step"] == 6
        assert tracker["cycles"] == 1


# ============================================================================
# Change 7: Autopilot Activation Decision Log (sot_manager tests)
# ============================================================================

class TestActivationDecisionLog:
    """Tests for activation decision log in cmd_set_autopilot."""

    def test_activation_log_created_on_first_enable(self, sot_mod, tmp_project_with_sot):
        """First autopilot enable → activation-decision.md created."""
        pd = str(tmp_project_with_sot)
        sot_mod.cmd_set_autopilot(pd, "true")
        log_path = os.path.join(pd, "autopilot-logs", "activation-decision.md")
        assert os.path.exists(log_path)
        with open(log_path, "r") as f:
            content = f.read()
        assert "Activation" in content
        assert "Test Workflow" in content

    def test_activation_log_not_overwritten(self, sot_mod, tmp_project_with_sot):
        """Second enable → log not overwritten."""
        pd = str(tmp_project_with_sot)
        sot_mod.cmd_set_autopilot(pd, "true")
        log_path = os.path.join(pd, "autopilot-logs", "activation-decision.md")
        assert os.path.exists(log_path)
        original_size = os.path.getsize(log_path)
        # Disable and re-enable
        sot_mod.cmd_set_autopilot(pd, "false")
        sot_mod.cmd_set_autopilot(pd, "true")
        assert os.path.getsize(log_path) == original_size  # Not overwritten

    def test_no_log_on_disable(self, sot_mod, tmp_project_with_sot):
        """Disabling autopilot → no activation log created."""
        pd = str(tmp_project_with_sot)
        sot_mod.cmd_set_autopilot(pd, "false")
        log_path = os.path.join(pd, "autopilot-logs", "activation-decision.md")
        assert not os.path.exists(log_path)


# ============================================================================
# Change 8: Auto-Approved Steps Audit Trail (sot_manager tests)
# ============================================================================

class TestAutoApprovedDetails:
    """Tests for auto_approved_details audit trail."""

    def test_details_recorded_on_approval(self, sot_mod, tmp_project_with_sot):
        """auto_approved_details dict populated with timestamp and log path."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 8)
        sot_mod.cmd_add_auto_approved(pd, 8)
        # Read SOT to check details
        result = sot_mod.cmd_read(pd)
        ap = result["workflow"]["autopilot"]
        details = ap.get("auto_approved_details", {})
        assert "8" in details
        assert "timestamp" in details["8"]
        assert "decision_log" in details["8"]
        assert "step-8-decision.md" in details["8"]["decision_log"]

    def test_details_in_initial_schema(self, sot_mod, tmp_path):
        """cmd_init includes auto_approved_details: {} in schema."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        result = sot_mod.cmd_init(str(tmp_path), "Test", 20)
        assert result["valid"]
        read_result = sot_mod.cmd_read(str(tmp_path))
        ap = read_result["workflow"]["autopilot"]
        assert "auto_approved_details" in ap
        assert ap["auto_approved_details"] == {}


# ============================================================================
# Change 9: Workflow Progress IMMORTAL Section
# ============================================================================

class TestWorkflowProgress:
    """Tests for _extract_workflow_progress() function."""

    def test_empty_when_no_sot(self, context_lib, tmp_path):
        """No SOT → empty progress lines."""
        result = context_lib._extract_workflow_progress(str(tmp_path))
        assert result == []

    def test_shows_completed_steps(self, context_lib, tmp_project_with_sot, sot_mod):
        """Completed steps with pACS logs are listed."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 3)
        _create_output(pd, "research/step-1.md")
        sot_mod.cmd_record_output(pd, 1, "research/step-1.md")
        _create_output(pd, "research/step-2.md")
        sot_mod.cmd_record_output(pd, 2, "research/step-2.md")
        # Create pACS log for step 1
        pacs_dir = os.path.join(pd, "pacs-logs")
        os.makedirs(pacs_dir, exist_ok=True)
        with open(os.path.join(pacs_dir, "step-1-pacs.md"), "w") as f:
            f.write("# pACS\npACS = 72\n" + "x" * 200)
        result = context_lib._extract_workflow_progress(pd)
        assert len(result) >= 2  # At least step-1 + current step
        assert any("Step 1" in line and "✓" in line for line in result)
        assert any("Step 3" in line and "현재" in line for line in result)

    def test_current_step_marked(self, context_lib, tmp_project_with_sot, sot_mod):
        """Current step is marked as in-progress."""
        pd = str(tmp_project_with_sot)
        _enable_autopilot_at_step(sot_mod, pd, 5)
        _create_output(pd, "research/step-3.md")
        sot_mod.cmd_record_output(pd, 3, "research/step-3.md")
        result = context_lib._extract_workflow_progress(pd)
        assert any("현재 진행중" in line for line in result)


# ============================================================================
# Change 10: Team State Restoration at SessionStart
# ============================================================================

class TestTeamStateRestoration:
    """Tests for team state surfacing in _build_recovery_output."""

    def test_team_state_surfaced_when_active(self, sot_mod, tmp_project_with_sot):
        """Active team in SOT → team state appears in recovery output."""
        import yaml
        pd = str(tmp_project_with_sot)
        sot_path = sot_mod._sot_path(pd)
        with open(sot_path, "r") as f:
            data = yaml.safe_load(f)
        data["workflow"]["active_team"] = {
            "name": "test-team",
            "status": "partial",
            "tasks_completed": ["task-1"],
            "tasks_pending": ["task-2"],
            "completed_summaries": {},
        }
        with open(sot_path, "w") as f:
            yaml.dump(data, f)

        # Test read_active_team_state directly (since restore_context needs full infrastructure)
        from _context_lib import read_active_team_state
        team = read_active_team_state(pd)
        assert team is not None
        assert team["name"] == "test-team"
        assert team["status"] == "partial"

    def test_no_team_state_when_no_team(self, context_lib, tmp_project_with_sot):
        """No active_team in SOT → returns None."""
        pd = str(tmp_project_with_sot)
        team = context_lib.read_active_team_state(pd)
        assert team is None


# ============================================================================
# Change 11: Autopilot Decision History in Snapshot
# ============================================================================

class TestDecisionHistory:
    """Tests for _extract_autopilot_decisions() function."""

    def test_empty_when_no_logs(self, context_lib, tmp_path):
        """No autopilot-logs → empty list."""
        result = context_lib._extract_autopilot_decisions(str(tmp_path))
        assert result == []

    def test_extracts_decisions(self, context_lib, tmp_path):
        """Decision logs present → extracts step, decision, rationale."""
        _create_decision_log(str(tmp_path), 4, size=200, template=True)
        _create_decision_log(str(tmp_path), 8, size=200, template=True)
        result = context_lib._extract_autopilot_decisions(str(tmp_path))
        assert len(result) == 2
        assert any("Step 4" in line for line in result)
        assert any("Step 8" in line for line in result)


# ============================================================================
# S5b: workflow_status "completed" cross-validation
# ============================================================================

class TestS5bCompletionCrossValidation:
    """S5b: completed status must have current_step >= total_steps."""

    def test_completed_with_insufficient_steps(self, context_lib):
        """S5b WARN: completed but current_step < total_steps."""
        ap = {
            "current_step": 5,
            "total_steps": 20,
            "workflow_status": "completed",
        }
        warnings = context_lib.validate_sot_schema(ap)
        assert any("current_step=5 < total_steps=20" in w for w in warnings)

    def test_completed_at_final_step_no_warning(self, context_lib):
        """S5b: completed + current_step == total_steps → no warning."""
        ap = {
            "current_step": 20,
            "total_steps": 20,
            "workflow_status": "completed",
        }
        warnings = context_lib.validate_sot_schema(ap)
        assert not any("current_step" in w and "total_steps" in w for w in warnings)

    def test_in_progress_no_cross_validation(self, context_lib):
        """S5b: non-completed status does not trigger cross-validation."""
        ap = {
            "current_step": 5,
            "total_steps": 20,
            "workflow_status": "in_progress",
        }
        warnings = context_lib.validate_sot_schema(ap)
        assert not any("total_steps" in w for w in warnings)


# ============================================================================
# TM: Team Merge Validation
# ============================================================================

class TestTeamMergeValidation:
    """Tests for validate_team_merge() function."""

    def test_no_active_team(self, context_lib, tmp_path):
        """TM1: No active_team in SOT → skip with warning."""
        result = context_lib.validate_team_merge(str(tmp_path), 10, "output.md")
        assert result["valid"] is True
        assert any("TM1" in w for w in result["warnings"])

    def test_missing_contributions(self, context_lib, tmp_path):
        """TM5: Output file missing teammate contributions → FAIL."""
        import yaml
        # Create SOT with active_team
        sot_dir = tmp_path / ".claude"
        sot_dir.mkdir(parents=True)
        sot_data = {
            "workflow": {
                "name": "Test",
                "current_step": 10,
                "total_steps": 20,
                "status": "in_progress",
                "outputs": {},
                "active_team": {
                    "name": "test-team",
                    "status": "all_completed",
                    "tasks_completed": ["adapter-kr", "adapter-en", "adapter-jp"],
                    "tasks_pending": [],
                    "completed_summaries": {
                        "adapter-kr": {"agent": "@adapter-dev-kr", "output": "kr-output.md"},
                        "adapter-en": {"agent": "@adapter-dev-en", "output": "en-output.md"},
                        "adapter-jp": {"agent": "@adapter-dev-jp", "output": "jp-output.md"},
                    },
                },
            }
        }
        with open(sot_dir / "state.yaml", "w") as f:
            yaml.dump(sot_data, f)

        # Create output file mentioning only kr and en
        out = tmp_path / "merged-output.md"
        out.write_text("# Merged\n## adapter-kr section\n## adapter-en section\n")

        result = context_lib.validate_team_merge(str(tmp_path), 10, str(out))
        assert result["valid"] is False
        assert "adapter-jp" in result["missing"]
        assert result["checked"] == 3

    def test_all_contributions_present(self, context_lib, tmp_path):
        """TM: All contributions present → PASS."""
        import yaml
        sot_dir = tmp_path / ".claude"
        sot_dir.mkdir(parents=True)
        sot_data = {
            "workflow": {
                "name": "Test",
                "current_step": 10,
                "total_steps": 20,
                "status": "in_progress",
                "outputs": {},
                "active_team": {
                    "name": "test-team",
                    "status": "all_completed",
                    "tasks_completed": ["task-a", "task-b"],
                    "tasks_pending": [],
                    "completed_summaries": {
                        "task-a": {"agent": "@dev-a", "output": "a.md"},
                        "task-b": {"agent": "@dev-b", "output": "b.md"},
                    },
                },
            }
        }
        with open(sot_dir / "state.yaml", "w") as f:
            yaml.dump(sot_data, f)

        out = tmp_path / "merged.md"
        out.write_text("# Merged\n## task-a results\n## task-b results\n")

        result = context_lib.validate_team_merge(str(tmp_path), 10, str(out))
        assert result["valid"] is True
        assert result["checked"] == 2
        assert result["missing"] == []


# ============================================================================
# Gap C: Verification outcomes in KA
# ============================================================================

class TestVerificationOutcomesKA:
    """Tests for _extract_verification_outcomes() — KI archiving."""

    def test_no_dir_returns_none(self, context_lib, tmp_path):
        """No verification-logs dir → None."""
        assert context_lib._extract_verification_outcomes(str(tmp_path)) is None

    def test_extracts_pass_fail(self, context_lib, tmp_path):
        """Extracts PASS/FAIL from verification logs."""
        vdir = tmp_path / "verification-logs"
        vdir.mkdir()
        (vdir / "step-3-verify.md").write_text("# Verification\nResult: PASS\nAll criteria met.")
        (vdir / "step-5-verify.md").write_text("# Verification\nStatus: FAIL\nMissing coverage.")
        result = context_lib._extract_verification_outcomes(str(tmp_path))
        assert result["step_3"]["result"] == "PASS"
        assert result["step_5"]["result"] == "FAIL"


# ============================================================================
# Gap D: Review outcomes in KA
# ============================================================================

class TestReviewOutcomesKA:
    """Tests for _extract_review_outcomes() — KI archiving."""

    def test_no_dir_returns_none(self, context_lib, tmp_path):
        """No review-logs dir → None."""
        assert context_lib._extract_review_outcomes(str(tmp_path)) is None

    def test_extracts_verdict_and_issues(self, context_lib, tmp_path):
        """Extracts verdict + issue counts from review logs."""
        rdir = tmp_path / "review-logs"
        rdir.mkdir()
        (rdir / "step-3-review.md").write_text(
            "# Review\nVerdict: PASS\nCritical: 0\nWarning: 2\nSuggestion: 5"
        )
        result = context_lib._extract_review_outcomes(str(tmp_path))
        assert result["step_3"]["verdict"] == "PASS"
        assert result["step_3"]["issues"]["warning"] == 2
        assert result["step_3"]["issues"]["suggestion"] == 5


# ============================================================================
# Gap G: Workflow quality summary in KA
# ============================================================================

class TestWorkflowQualitySummaryKA:
    """Tests for _extract_workflow_quality_summary() — KI archiving."""

    def test_no_dir_returns_none(self, context_lib, tmp_path):
        """No pacs-logs dir → None."""
        assert context_lib._extract_workflow_quality_summary(str(tmp_path)) is None

    def test_extracts_scores_and_grades(self, context_lib, tmp_path):
        """Extracts pACS score + color grade from pacs logs."""
        pdir = tmp_path / "pacs-logs"
        pdir.mkdir()
        (pdir / "step-3-pacs.md").write_text(
            "# pACS\npACS: 72\n## Assessment\nOverall: YELLOW\n"
        )
        (pdir / "step-5-pacs.md").write_text(
            "# pACS\npACS: 85\n## Assessment\nOverall: GREEN\n"
        )
        result = context_lib._extract_workflow_quality_summary(str(tmp_path))
        assert result["step_3"]["score"] == 72
        assert result["step_3"]["grade"] == "YELLOW"
        assert result["step_5"]["score"] == 85
        assert result["step_5"]["grade"] == "GREEN"


# ============================================================================
# Gap E: Retry Budget IMMORTAL
# ============================================================================

class TestRetryBudgetIMMORTAL:
    """Tests for _extract_retry_budget_state() — IMMORTAL preservation."""

    def test_no_retries_returns_empty(self, context_lib, tmp_path):
        """No retry count files → empty list."""
        (tmp_path / "verification-logs").mkdir()
        result = context_lib._extract_retry_budget_state(str(tmp_path))
        assert result == []

    def test_extracts_retry_state(self, context_lib, tmp_path):
        """Active retry counts → extracted with gate info."""
        vdir = tmp_path / "verification-logs"
        vdir.mkdir()
        (vdir / ".step-5-retry-count").write_text("3")
        # Add history file
        import json
        hist = vdir / ".step-5-retry-history.jsonl"
        hist.write_text(json.dumps({"attempt": 3, "pacs_score": 62}) + "\n")

        result = context_lib._extract_retry_budget_state(str(tmp_path))
        assert len(result) == 1
        assert "verification" in result[0]
        assert "Step 5" in result[0]
        assert "3 retries" in result[0]
        assert "62" in result[0]


# ============================================================================
# Gap F: Instruction surfacing at SessionStart
# ============================================================================

class TestInstructionSurfacing:
    """Tests for Gap F — latest instruction extraction from snapshot."""

    def test_instruction_from_snapshot_content(self):
        """Extract latest instruction from snapshot content when summary lacks it."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "restore_context",
            os.path.join(HOOKS_DIR, "restore_context.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        snapshot_content = (
            "## 현재 작업\nSome task\n\n"
            "**최근 지시 (Latest Instruction):** 코드베이스를 검수하고 성찰한다.\n"
            "특히 Task 관리 시스템이 중요하다.\n"
            "context memory 최적화도 수행하라.\n"
        )
        # summary without latest_instruction
        summary = [("현재 작업", "Some task")]
        output = mod._build_recovery_output(
            source="compact",
            latest_path="/tmp/latest.md",
            summary=summary,
            sot_warning="",
            snapshot_age=120,
            snapshot_content=snapshot_content,
        )
        assert "코드베이스를 검수하고 성찰한다" in output

    def test_summary_instruction_takes_priority(self):
        """When summary has latest_instruction, skip snapshot extraction."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "restore_context",
            os.path.join(HOOKS_DIR, "restore_context.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        summary = [
            ("현재 작업", "Some task"),
            ("최근 지시", "Summary instruction"),
        ]
        output = mod._build_recovery_output(
            source="compact",
            latest_path="/tmp/latest.md",
            summary=summary,
            sot_warning="",
            snapshot_age=60,
            snapshot_content="**최근 지시 (Latest Instruction):** Snapshot instruction",
        )
        assert "Summary instruction" in output
        # Should not duplicate with snapshot extraction
        assert output.count("최근 지시") == 1


# ============================================================================
# Gap H: Stall detection integration in run_quality_gates
# ============================================================================

class TestStallDetectionIntegration:
    """Tests for stall detection integration in check_quality_gates()."""

    def test_stall_detection_runs_in_quality_gates(self):
        """check_quality_gates() includes stall_detection gate."""
        mod = _import_script("run_quality_gates")
        import tempfile
        td = tempfile.mkdtemp()
        # Just verify gate key is present (will be SKIP without proper setup)
        result = mod.check_quality_gates(td, 3)
        assert "stall_detection" in result["gates"]

    def test_stall_detection_no_false_positive(self):
        """Fresh project → stall detection OK (no stall)."""
        mod = _import_script("run_quality_gates")
        import tempfile
        td = tempfile.mkdtemp()
        os.makedirs(os.path.join(td, "autopilot-logs"), exist_ok=True)
        result = mod.check_quality_gates(td, 3)
        # Should be OK or SKIP, not WARNING
        assert result["gates"].get("stall_detection") in ("OK", "SKIP")
