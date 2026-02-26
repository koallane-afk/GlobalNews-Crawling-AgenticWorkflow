"""Structural validation tests — Orchestrator Playbook structure.

Tests verify:
- Phase E: Playbook has Verification criteria reference to prompt/workflow.md
- Phase E: Playbook has Agent Spawn Protocol
- Quick Reference table completeness
- Universal Step Protocol completeness
- SOT Command Cheat Sheet
- All 20 steps referenced
"""

import os
import re

import pytest


@pytest.fixture
def playbook_content(project_root):
    path = os.path.join(project_root, "ORCHESTRATOR-PLAYBOOK.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# Phase E: Verification Criteria Reference
# ============================================================================

class TestVerificationReference:
    """Verify Playbook references prompt/workflow.md for Verification criteria."""

    def test_has_verification_criteria_source(self, playbook_content):
        """Phase E: Must explicitly reference prompt/workflow.md."""
        assert "prompt/workflow.md" in playbook_content

    def test_verification_source_near_universal_protocol(self, playbook_content):
        """The reference should be near the Universal Step Protocol."""
        # Find both anchors
        protocol_pos = playbook_content.find("Universal Step Protocol")
        source_pos = playbook_content.find("Verification Criteria Source")
        assert protocol_pos > 0, "Universal Step Protocol section missing"
        assert source_pos > 0, "Verification Criteria Source note missing"
        # Source should be within 2000 chars of the protocol
        assert abs(source_pos - protocol_pos) < 2000


# ============================================================================
# Phase E: Agent Spawn Protocol
# ============================================================================

class TestAgentSpawnProtocol:
    """Verify Playbook has Agent Spawn Protocol section."""

    def test_has_agent_spawn_section(self, playbook_content):
        assert "Agent Spawn Protocol" in playbook_content

    def test_has_solo_agent_example(self, playbook_content):
        """Should show how to spawn a solo agent."""
        assert "Solo agent" in playbook_content or "solo agent" in playbook_content

    def test_has_team_example(self, playbook_content):
        """Should show how to create a team."""
        assert "TeamCreate" in playbook_content


# ============================================================================
# Quick Reference Table
# ============================================================================

class TestQuickReference:
    """Verify Quick Reference table lists all key scripts."""

    def test_has_sot_manager(self, playbook_content):
        assert "sot_manager.py" in playbook_content

    def test_has_run_quality_gates(self, playbook_content):
        assert "run_quality_gates.py" in playbook_content

    def test_has_validate_step_transition(self, playbook_content):
        assert "validate_step_transition.py" in playbook_content

    def test_has_extract_step_guide(self, playbook_content):
        assert "extract_orchestrator_step_guide.py" in playbook_content


# ============================================================================
# Universal Step Protocol
# ============================================================================

class TestUniversalStepProtocol:
    """Verify the Universal Step Protocol is complete."""

    def test_has_read_sot_step(self, playbook_content):
        assert "READ SOT" in playbook_content

    def test_has_quality_gates_step(self, playbook_content):
        assert "Quality Gates" in playbook_content
        assert "L0" in playbook_content
        assert "L1" in playbook_content
        assert "L1.5" in playbook_content

    def test_has_translation_step(self, playbook_content):
        assert "Translation" in playbook_content

    def test_has_validate_transition_step(self, playbook_content):
        assert "validate_step_transition" in playbook_content

    def test_has_advance_step(self, playbook_content):
        assert "advance-step" in playbook_content


# ============================================================================
# SOT Command Cheat Sheet
# ============================================================================

class TestSOTCheatSheet:
    """Verify SOT Command Cheat Sheet is complete."""

    def test_has_read_command(self, playbook_content):
        assert "--read" in playbook_content

    def test_has_record_output_command(self, playbook_content):
        assert "--record-output" in playbook_content

    def test_has_advance_step_command(self, playbook_content):
        assert "--advance-step" in playbook_content

    def test_has_update_pacs_command(self, playbook_content):
        assert "--update-pacs" in playbook_content

    def test_has_update_team_command(self, playbook_content):
        assert "--update-team" in playbook_content

    def test_has_set_status_command(self, playbook_content):
        assert "--set-status" in playbook_content


# ============================================================================
# Step Coverage
# ============================================================================

class TestStepCoverage:
    """Verify all 20 steps are referenced in the Playbook."""

    def test_all_20_steps_referenced(self, playbook_content):
        """Each step 1-20 should appear as 'Step N' in the playbook."""
        for n in range(1, 21):
            pattern = f"Step {n}"
            assert pattern in playbook_content, \
                f"Step {n} not found in playbook"

    def test_has_research_phase(self, playbook_content):
        assert "Research Phase" in playbook_content

    def test_has_planning_phase(self, playbook_content):
        assert "Planning Phase" in playbook_content


# ============================================================================
# Team JSON Format
# ============================================================================

class TestTeamJsonFormat:
    """Verify Team JSON examples in Playbook are valid JSON."""

    def test_team_json_examples_parseable(self, playbook_content):
        """All --update-team JSON strings should be valid JSON."""
        import json
        # Find all --update-team '{...}' patterns
        pattern = re.compile(r"--update-team\s+'(\{[^']+\})'")
        matches = pattern.findall(playbook_content)

        assert len(matches) > 0, "No --update-team JSON examples found"

        for i, json_str in enumerate(matches):
            try:
                data = json.loads(json_str)
                assert "name" in data, f"Team JSON #{i+1} missing 'name'"
                assert "status" in data, f"Team JSON #{i+1} missing 'status'"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid Team JSON #{i+1}: {e}\nJSON: {json_str[:100]}...")
