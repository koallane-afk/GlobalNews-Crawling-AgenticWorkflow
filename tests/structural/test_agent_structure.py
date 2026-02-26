"""Structural validation tests — Agent .md file structure.

Tests verify:
- Phase D: All agents have required sections (Language Rule, Protocol, Quality Checklist)
- Adapter agents have Non-Interference Rule
- YAML frontmatter is valid
- Consistency across agent definitions
"""

import os
import re

import pytest


def _read_agent(agents_dir, filename):
    """Read an agent markdown file and return its content."""
    path = os.path.join(agents_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_frontmatter(content):
    """Extract YAML frontmatter from agent file."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm


# ============================================================================
# Agent File Existence
# ============================================================================

CORE_AGENTS = [
    "reviewer.md",
    "fact-checker.md",
    "translator.md",
]

ADAPTER_AGENTS = [
    "adapter-dev-kr-major.md",
    "adapter-dev-kr-tech.md",
    "adapter-dev-english.md",
    "adapter-dev-multilingual.md",
]

ALL_AGENTS = CORE_AGENTS + ADAPTER_AGENTS


class TestAgentFileExistence:
    """Verify all agent files exist."""

    @pytest.mark.parametrize("filename", ALL_AGENTS)
    def test_agent_file_exists(self, agents_dir, filename):
        path = os.path.join(agents_dir, filename)
        assert os.path.exists(path), f"Agent file missing: {filename}"


# ============================================================================
# YAML Frontmatter
# ============================================================================

class TestFrontmatter:
    """Verify agent frontmatter structure."""

    @pytest.mark.parametrize("filename", ALL_AGENTS)
    def test_has_frontmatter(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert content.startswith("---"), f"{filename} missing frontmatter"

    @pytest.mark.parametrize("filename", ALL_AGENTS)
    def test_frontmatter_has_name(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        fm = _parse_frontmatter(content)
        assert "name" in fm, f"{filename} missing 'name' in frontmatter"

    @pytest.mark.parametrize("filename", ALL_AGENTS)
    def test_frontmatter_has_model(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        fm = _parse_frontmatter(content)
        assert "model" in fm, f"{filename} missing 'model' in frontmatter"

    @pytest.mark.parametrize("filename", ALL_AGENTS)
    def test_frontmatter_has_tools(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        fm = _parse_frontmatter(content)
        assert "tools" in fm, f"{filename} missing 'tools' in frontmatter"


# ============================================================================
# Required Sections — Core Agents (Phase D)
# ============================================================================

class TestCoreAgentSections:
    """Verify core agents have required structural sections."""

    @pytest.mark.parametrize("filename", CORE_AGENTS)
    def test_has_absolute_rules(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Absolute Rules" in content, f"{filename} missing Absolute Rules"

    @pytest.mark.parametrize("filename", CORE_AGENTS)
    def test_has_language_rule(self, agents_dir, filename):
        """Phase D: All core agents must have Language Rule section."""
        content = _read_agent(agents_dir, filename)
        assert "## Language Rule" in content, f"{filename} missing Language Rule"

    @pytest.mark.parametrize("filename", CORE_AGENTS)
    def test_has_protocol_mandatory(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "Protocol" in content and "MANDATORY" in content, \
            f"{filename} missing Protocol (MANDATORY) section"

    @pytest.mark.parametrize("filename", ["reviewer.md", "fact-checker.md"])
    def test_has_never_do(self, agents_dir, filename):
        """reviewer and fact-checker require NEVER DO. translator's prohibitions are in Absolute Rules."""
        content = _read_agent(agents_dir, filename)
        assert "## NEVER DO" in content, f"{filename} missing NEVER DO section"

    @pytest.mark.parametrize("filename", ["fact-checker.md", "reviewer.md"])
    def test_has_quality_checklist(self, agents_dir, filename):
        """Phase D: fact-checker and reviewer must have Quality Checklist."""
        content = _read_agent(agents_dir, filename)
        assert "## Quality Checklist" in content, f"{filename} missing Quality Checklist"


# ============================================================================
# Required Sections — Adapter Agents (Phase D)
# ============================================================================

class TestAdapterAgentSections:
    """Verify adapter agents have required structural sections."""

    @pytest.mark.parametrize("filename", ADAPTER_AGENTS)
    def test_has_absolute_rules(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Absolute Rules" in content

    @pytest.mark.parametrize("filename", ADAPTER_AGENTS)
    def test_has_language_rule(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Language Rule" in content

    @pytest.mark.parametrize("filename", ADAPTER_AGENTS)
    def test_has_protocol_mandatory(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Protocol (MANDATORY)" in content

    @pytest.mark.parametrize("filename", ADAPTER_AGENTS)
    def test_has_quality_checklist(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Quality Checklist" in content

    @pytest.mark.parametrize("filename", ADAPTER_AGENTS)
    def test_has_team_collaboration(self, agents_dir, filename):
        content = _read_agent(agents_dir, filename)
        assert "## Team Collaboration" in content

    @pytest.mark.parametrize("filename", [
        "adapter-dev-kr-tech.md",
        "adapter-dev-english.md",
        "adapter-dev-multilingual.md",
    ])
    def test_has_non_interference_rule(self, agents_dir, filename):
        """Phase D: 3 adapter agents must have Non-Interference Rule."""
        content = _read_agent(agents_dir, filename)
        assert "## Non-Interference Rule" in content, \
            f"{filename} missing Non-Interference Rule"

    def test_kr_major_has_explicit_site_count(self, agents_dir):
        """adapter-dev-kr-major should state exactly 11 sites."""
        content = _read_agent(agents_dir, "adapter-dev-kr-major.md")
        assert "11" in content

    def test_kr_tech_has_explicit_site_count(self, agents_dir):
        content = _read_agent(agents_dir, "adapter-dev-kr-tech.md")
        assert "8" in content

    def test_english_has_explicit_site_count(self, agents_dir):
        content = _read_agent(agents_dir, "adapter-dev-english.md")
        assert "12" in content

    def test_multilingual_has_explicit_site_count(self, agents_dir):
        content = _read_agent(agents_dir, "adapter-dev-multilingual.md")
        assert "13" in content


# ============================================================================
# Read-Only Enforcement
# ============================================================================

class TestReadOnlyAgents:
    """Verify read-only agents don't have write tools."""

    def test_reviewer_no_write_tools(self, agents_dir):
        content = _read_agent(agents_dir, "reviewer.md")
        fm = _parse_frontmatter(content)
        tools = fm.get("tools", "")
        assert "Write" not in tools
        assert "Edit" not in tools
        assert "Bash" not in tools

    def test_fact_checker_no_write_tools(self, agents_dir):
        content = _read_agent(agents_dir, "fact-checker.md")
        fm = _parse_frontmatter(content)
        tools = fm.get("tools", "")
        assert "Write" not in tools
        assert "Edit" not in tools
        assert "Bash" not in tools


# ============================================================================
# Translator-Specific
# ============================================================================

class TestTranslatorAgent:
    """Translator-specific structural tests."""

    def test_has_glossary_reference(self, agents_dir):
        content = _read_agent(agents_dir, "translator.md")
        assert "glossary.yaml" in content

    def test_has_translation_pacs(self, agents_dir):
        content = _read_agent(agents_dir, "translator.md")
        assert "Ft" in content and "Ct" in content and "Nt" in content

    def test_has_self_review_step(self, agents_dir):
        content = _read_agent(agents_dir, "translator.md")
        assert "Self-Review" in content
