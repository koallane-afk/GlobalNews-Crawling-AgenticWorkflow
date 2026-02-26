"""Unit tests for setup_init.py — Phase C: Project Structure.

Tests verify:
- Workflow output directories created when SOT exists
- Directories NOT created when SOT is absent
- All 6 log directories + 6 workflow directories are handled
"""

import importlib.util
import os
import sys

import pytest

# Import setup_init from hooks directory
HOOKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".claude", "hooks", "scripts",
)


def _import_setup_init():
    spec = importlib.util.spec_from_file_location(
        "setup_init", os.path.join(HOOKS_DIR, "setup_init.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Workflow Output Directory Tests (Phase C)
# ============================================================================

class TestWorkflowOutputDirs:
    """Test _check_workflow_output_dirs function."""

    def test_dirs_created_when_sot_exists(self, tmp_path):
        """When SOT exists, workflow dirs should be auto-created."""
        mod = _import_setup_init()
        # Create SOT file
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "state.yaml").write_text("workflow:\n  current_step: 1\n")

        results = mod._check_workflow_output_dirs(str(tmp_path))

        # Should have results for each directory
        assert len(results) >= 6

        # All should pass
        for r in results:
            assert r["status"] == "PASS", f"Failed: {r['check']}: {r['message']}"

        # Verify directories exist
        expected_dirs = ["research", "planning", "testing", "docs", "config"]
        for dirname in expected_dirs:
            assert (tmp_path / dirname).is_dir(), f"{dirname}/ not created"

    def test_dirs_not_created_without_sot(self, tmp_path):
        """When no SOT exists, no workflow dirs should be created."""
        mod = _import_setup_init()
        # Create .claude dir but NO state.yaml
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        results = mod._check_workflow_output_dirs(str(tmp_path))

        # Should return empty list (no SOT = no dirs needed)
        assert results == []

    def test_existing_dirs_not_recreated(self, tmp_path):
        """Pre-existing dirs should be recognized without error."""
        mod = _import_setup_init()
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "state.yaml").write_text("workflow:\n  current_step: 1\n")

        # Pre-create some dirs
        (tmp_path / "research").mkdir()
        (tmp_path / "planning").mkdir()

        results = mod._check_workflow_output_dirs(str(tmp_path))

        for r in results:
            assert r["status"] == "PASS"

    def test_planning_team_input_subdir(self, tmp_path):
        """planning/team-input/ should also be created."""
        mod = _import_setup_init()
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "state.yaml").write_text("workflow:\n  current_step: 1\n")

        mod._check_workflow_output_dirs(str(tmp_path))

        assert (tmp_path / "planning" / "team-input").is_dir()


# ============================================================================
# Runtime Directory Tests (existing feature)
# ============================================================================

class TestRuntimeDirs:
    """Test _check_runtime_dirs function (existing feature verification)."""

    def test_runtime_dirs_created_when_sot_exists(self, tmp_path):
        mod = _import_setup_init()
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "state.yaml").write_text("workflow:\n  current_step: 1\n")

        results = mod._check_runtime_dirs(str(tmp_path))

        expected = [
            "verification-logs", "pacs-logs", "review-logs",
            "autopilot-logs", "translations", "diagnosis-logs",
        ]
        for dirname in expected:
            assert (tmp_path / dirname).is_dir(), f"{dirname}/ not created"

    def test_runtime_dirs_skip_without_sot(self, tmp_path):
        mod = _import_setup_init()
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        results = mod._check_runtime_dirs(str(tmp_path))
        assert results == []


# ============================================================================
# Script Validation Tests
# ============================================================================

class TestScriptValidation:
    """Test _check_script function."""

    def test_valid_script_passes(self, tmp_path):
        mod = _import_setup_init()
        script = tmp_path / "valid.py"
        script.write_text("import os\nprint('hello')\n")
        result = mod._check_script(str(tmp_path), "valid.py")
        assert result["status"] == "PASS"

    def test_syntax_error_fails(self, tmp_path):
        mod = _import_setup_init()
        script = tmp_path / "bad.py"
        script.write_text("def foo(:\n  pass\n")
        result = mod._check_script(str(tmp_path), "bad.py")
        assert result["status"] == "FAIL"
        assert result["severity"] == "CRITICAL"

    def test_missing_script_fails(self, tmp_path):
        mod = _import_setup_init()
        result = mod._check_script(str(tmp_path), "nonexistent.py")
        assert result["status"] == "FAIL"
