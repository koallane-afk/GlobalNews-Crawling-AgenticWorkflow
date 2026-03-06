"""Unit tests for setup_init.py — Phase C: Project Structure + Domain Venv.

Tests verify:
- Workflow output directories created when SOT exists
- Directories NOT created when SOT is absent
- All 6 log directories + 6 workflow directories are handled
- Domain venv health checks (ENV1a-ENV1d)
"""

import importlib.util
import os
import sys
from unittest.mock import patch, MagicMock

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


# ============================================================================
# Domain Venv Tests (ENV1a-ENV1d)
# ============================================================================

class TestDomainVenv:
    """Test _check_domain_venv function (P1 — ENV1a-ENV1d)."""

    def test_env1a_no_venv_dir(self, tmp_path):
        """ENV1a: Missing .venv/ directory → WARNING FAIL."""
        mod = _import_setup_init()
        results = mod._check_domain_venv(str(tmp_path))

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert results[0]["severity"] == "WARNING"
        assert "ENV1a" in results[0]["check"]
        assert ".venv/ not found" in results[0]["message"]

    def test_env1b_no_python_binary(self, tmp_path):
        """ENV1b: .venv/ exists but bin/python missing → WARNING FAIL."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        # Don't create bin/python

        results = mod._check_domain_venv(str(tmp_path))

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert "ENV1b" in results[0]["check"]
        assert "not found" in results[0]["message"]

    def test_env1b_wrong_python_version(self, tmp_path):
        """ENV1b: Python 3.14 in venv → WARNING FAIL (version out of range)."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        mock_result = MagicMock()
        mock_result.stdout = "Python 3.14.0"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            results = mod._check_domain_venv(str(tmp_path))

        # Should have ENV1b FAIL for wrong version
        env1b = [r for r in results if "ENV1b" in r["check"]]
        assert len(env1b) == 1
        assert env1b[0]["status"] == "FAIL"
        assert "3.12 or 3.13 required" in env1b[0]["message"]

    def test_env1b_unparseable_version(self, tmp_path):
        """ENV1b: Cannot parse version string → WARNING FAIL."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        mock_result = MagicMock()
        mock_result.stdout = "Something unexpected"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            results = mod._check_domain_venv(str(tmp_path))

        env1b = [r for r in results if "ENV1b" in r["check"]]
        assert len(env1b) == 1
        assert env1b[0]["status"] == "FAIL"
        assert "Cannot parse" in env1b[0]["message"]

    def test_env1b_subprocess_timeout(self, tmp_path):
        """ENV1b: subprocess.run times out → WARNING FAIL."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="python", timeout=10)):
            results = mod._check_domain_venv(str(tmp_path))

        env1b = [r for r in results if "ENV1b" in r["check"]]
        assert len(env1b) == 1
        assert env1b[0]["status"] == "FAIL"
        assert "Cannot execute" in env1b[0]["message"]

    def test_env1c_spacy_not_importable(self, tmp_path):
        """ENV1c: spaCy import fails in venv → WARNING FAIL."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        def mock_subprocess(cmd, **kwargs):
            result = MagicMock()
            if "--version" in cmd:
                result.stdout = "Python 3.13.12"
                result.stderr = ""
                result.returncode = 0
            elif "import spacy" in str(cmd):
                result.stdout = ""
                result.stderr = "ModuleNotFoundError: No module named 'spacy'"
                result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=mock_subprocess):
            results = mod._check_domain_venv(str(tmp_path))

        env1c = [r for r in results if "ENV1c" in r["check"]]
        assert len(env1c) == 1
        assert env1c[0]["status"] == "FAIL"
        assert "spaCy import failed" in env1c[0]["message"]

    def test_env1d_model_not_loadable(self, tmp_path):
        """ENV1d: en_core_web_sm model load fails → WARNING FAIL."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        call_count = [0]

        def mock_subprocess(cmd, **kwargs):
            result = MagicMock()
            if "--version" in cmd:
                result.stdout = "Python 3.13.12"
                result.stderr = ""
                result.returncode = 0
            elif "-c" in cmd:
                call_count[0] += 1
                if call_count[0] == 1:
                    # First -c call = ENV1c (spaCy import)
                    result.stdout = "3.8.11"
                    result.stderr = ""
                    result.returncode = 0
                else:
                    # Second -c call = ENV1d (model load)
                    result.stdout = ""
                    result.stderr = "OSError: Can't find model 'en_core_web_sm'"
                    result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=mock_subprocess):
            results = mod._check_domain_venv(str(tmp_path))

        env1d = [r for r in results if "ENV1d" in r["check"]]
        assert len(env1d) == 1
        assert env1d[0]["status"] == "FAIL"
        assert "en_core_web_sm load failed" in env1d[0]["message"]

    def test_all_checks_pass(self, tmp_path):
        """All ENV1a-ENV1d pass → 4 PASS results."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        def mock_subprocess(cmd, **kwargs):
            result = MagicMock()
            cmd_str = str(cmd)
            if "--version" in cmd:
                result.stdout = "Python 3.13.12"
                result.stderr = ""
                result.returncode = 0
            elif "import spacy; print" in cmd_str and "load" not in cmd_str:
                result.stdout = "3.8.11"
                result.stderr = ""
                result.returncode = 0
            elif "spacy.load" in cmd_str:
                result.stdout = "5 pipes"
                result.stderr = ""
                result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_subprocess):
            results = mod._check_domain_venv(str(tmp_path))

        assert len(results) == 3  # ENV1b, ENV1c, ENV1d (ENV1a is dir check, no result on pass)
        for r in results:
            assert r["status"] == "PASS", f"Failed: {r['check']}: {r['message']}"

    def test_python_312_also_passes(self, tmp_path):
        """ENV1b: Python 3.12 is also acceptable."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        def mock_subprocess(cmd, **kwargs):
            result = MagicMock()
            cmd_str = str(cmd)
            if "--version" in cmd:
                result.stdout = "Python 3.12.8"
                result.stderr = ""
                result.returncode = 0
            elif "import spacy; print" in cmd_str and "load" not in cmd_str:
                result.stdout = "3.8.11"
                result.stderr = ""
                result.returncode = 0
            elif "spacy.load" in cmd_str:
                result.stdout = "5 pipes"
                result.stderr = ""
                result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_subprocess):
            results = mod._check_domain_venv(str(tmp_path))

        env1b = [r for r in results if "ENV1b" in r["check"]]
        assert len(env1b) == 1
        assert env1b[0]["status"] == "PASS"
        assert "3.12.8" in env1b[0]["message"]

    def test_early_return_on_env1a_fail(self, tmp_path):
        """ENV1a fail should return immediately without checking ENV1b-d."""
        mod = _import_setup_init()
        # No .venv dir at all
        results = mod._check_domain_venv(str(tmp_path))

        assert len(results) == 1  # Only ENV1a, no further checks
        assert "ENV1a" in results[0]["check"]

    def test_early_return_on_env1b_fail(self, tmp_path):
        """ENV1b fail should return immediately without checking ENV1c-d."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        mock_result = MagicMock()
        mock_result.stdout = "Python 3.14.0"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            results = mod._check_domain_venv(str(tmp_path))

        # ENV1b FAIL only, no ENV1c/d
        assert len(results) == 1
        assert "ENV1b" in results[0]["check"]

    def test_early_return_on_env1c_fail(self, tmp_path):
        """ENV1c fail should return immediately without checking ENV1d."""
        mod = _import_setup_init()
        venv_dir = tmp_path / ".venv"
        (venv_dir / "bin").mkdir(parents=True)
        python_bin = venv_dir / "bin" / "python"
        python_bin.write_text("#!/bin/sh\n")
        python_bin.chmod(0o755)

        def mock_subprocess(cmd, **kwargs):
            result = MagicMock()
            if "--version" in cmd:
                result.stdout = "Python 3.13.12"
                result.stderr = ""
                result.returncode = 0
            elif "import spacy" in str(cmd):
                result.stdout = ""
                result.stderr = "ModuleNotFoundError"
                result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=mock_subprocess):
            results = mod._check_domain_venv(str(tmp_path))

        # ENV1b PASS + ENV1c FAIL, no ENV1d
        assert len(results) == 2
        checks = [r["check"] for r in results]
        assert any("ENV1b" in c for c in checks)
        assert any("ENV1c" in c for c in checks)
        assert not any("ENV1d" in c for c in checks)

    def test_all_results_are_warning_severity(self, tmp_path):
        """All results should be WARNING severity (not CRITICAL)."""
        mod = _import_setup_init()
        # Test ENV1a fail
        results = mod._check_domain_venv(str(tmp_path))
        for r in results:
            assert r["severity"] == "WARNING", (
                f"Expected WARNING but got {r['severity']} for {r['check']}"
            )
