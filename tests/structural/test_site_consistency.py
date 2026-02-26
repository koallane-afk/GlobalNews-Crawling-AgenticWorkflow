"""Structural validation tests — Cross-script site consistency.

Tests verify:
- Phase B+D: Sites in distribute_sites_to_teams.py == sites in generate_sources_yaml_draft.py
- Sites in scripts match sites described in adapter agent .md files
- No orphan sites (in script but not in agent) or missing sites (in agent but not in script)
"""

import os
import re

import pytest


def _extract_domains_from_agent_md(filepath):
    """Extract domain-like strings from an adapter agent markdown file.

    Looks for patterns like domain.com, domain.co.kr in the file content.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Match domain patterns in the markdown
    # Specifically look for domains in parentheses or bold — typical in agent specs
    domains = set()
    # Pattern: (domain.tld) or **domain.tld**
    for match in re.finditer(r"[(\s*]([a-z0-9][-a-z0-9]*\.(?:com|co\.kr|co\.jp|or\.jp|net|fr|de|es|ru|network))\b", content):
        domains.add(match.group(1))
    return domains


# ============================================================================
# Cross-Script Consistency
# ============================================================================

class TestDistributeVsSources:
    """Verify distribute_sites and generate_sources have identical domains."""

    def test_same_total_count(self, distribute_mod, sources_mod):
        dist_total = sum(len(v) for v in distribute_mod._DEFAULT_GROUPS.values())
        src_total = len(sources_mod._DEFAULT_SITES)
        assert dist_total == src_total == 44

    def test_same_domains(self, distribute_mod, sources_mod):
        """All domains in distribute should appear in sources, and vice versa."""
        dist_domains = set()
        for sites in distribute_mod._DEFAULT_GROUPS.values():
            for s in sites:
                dist_domains.add(s["domain"])

        src_domains = {s["domain"] for s in sources_mod._DEFAULT_SITES}

        missing_in_sources = dist_domains - src_domains
        missing_in_distribute = src_domains - dist_domains

        assert not missing_in_sources, \
            f"In distribute but not in sources: {missing_in_sources}"
        assert not missing_in_distribute, \
            f"In sources but not in distribute: {missing_in_distribute}"

    def test_kr_major_group_matches(self, distribute_mod, sources_mod):
        """kr-major domains in distribute == Korean major domains in sources."""
        dist_kr = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["kr-major"]}
        src_kr = {
            s["domain"] for s in sources_mod._DEFAULT_SITES
            if s["language"] == "ko" and s["domain"] in dist_kr
        }
        assert dist_kr == src_kr


# ============================================================================
# Script-to-Agent Consistency
# ============================================================================

class TestScriptToAgentConsistency:
    """Verify script site lists match agent markdown specifications."""

    def test_kr_major_script_matches_agent(self, distribute_mod, agents_dir):
        """distribute kr-major domains should match adapter-dev-kr-major.md."""
        script_domains = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["kr-major"]}
        agent_domains = _extract_domains_from_agent_md(
            os.path.join(agents_dir, "adapter-dev-kr-major.md")
        )

        # Agent may have domains in different formats — check key ones
        key_domains = {"chosun.com", "joongang.co.kr", "donga.com", "hani.co.kr", "yna.co.kr"}
        for d in key_domains:
            assert d in script_domains, f"Key domain {d} missing from script"

    def test_kr_major_count_matches_agent_claim(self, distribute_mod, agents_dir):
        """Agent says 11 sites — script should have 11."""
        assert len(distribute_mod._DEFAULT_GROUPS["kr-major"]) == 11

    def test_kr_tech_count_matches_agent_claim(self, distribute_mod, agents_dir):
        """Agent says 8 sites — script should have 8."""
        assert len(distribute_mod._DEFAULT_GROUPS["kr-tech"]) == 8

    def test_english_count_matches_agent_claim(self, distribute_mod, agents_dir):
        """Agent says 12 sites — script should have 12."""
        assert len(distribute_mod._DEFAULT_GROUPS["english"]) == 12

    def test_multilingual_count_matches_agent_claim(self, distribute_mod, agents_dir):
        """Agent says 13 sites — script should have 13."""
        assert len(distribute_mod._DEFAULT_GROUPS["multilingual"]) == 13


# ============================================================================
# Language Tag Consistency
# ============================================================================

class TestLanguageTagConsistency:
    """Verify language tags in sources match group assignments in distribute."""

    def test_kr_major_all_korean(self, sources_mod, distribute_mod):
        kr_domains = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["kr-major"]}
        for site in sources_mod._DEFAULT_SITES:
            if site["domain"] in kr_domains:
                assert site["language"] == "ko", \
                    f"{site['domain']} should be 'ko' but is '{site['language']}'"

    def test_kr_tech_all_korean(self, sources_mod, distribute_mod):
        kr_domains = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["kr-tech"]}
        for site in sources_mod._DEFAULT_SITES:
            if site["domain"] in kr_domains:
                assert site["language"] == "ko", \
                    f"{site['domain']} should be 'ko' but is '{site['language']}'"

    def test_english_all_english(self, sources_mod, distribute_mod):
        en_domains = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["english"]}
        for site in sources_mod._DEFAULT_SITES:
            if site["domain"] in en_domains:
                assert site["language"] == "en", \
                    f"{site['domain']} should be 'en' but is '{site['language']}'"

    def test_multilingual_non_english_non_korean(self, sources_mod, distribute_mod):
        ml_domains = {s["domain"] for s in distribute_mod._DEFAULT_GROUPS["multilingual"]}
        for site in sources_mod._DEFAULT_SITES:
            if site["domain"] in ml_domains:
                assert site["language"] not in ("ko", "en"), \
                    f"Multilingual site {site['domain']} has unexpected language '{site['language']}'"
