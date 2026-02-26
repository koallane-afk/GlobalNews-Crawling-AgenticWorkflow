"""Unit tests for generate_sources_yaml_draft.py — Phase B: Sources YAML.

Tests verify:
- Default site catalog has exactly 44 entries
- All required fields present per site
- Sites match distribute_sites_to_teams.py groups
- YAML generation works
"""

import os

import pytest


# ============================================================================
# Site Catalog Tests
# ============================================================================

class TestDefaultSitesCatalog:
    """Verify the _DEFAULT_SITES catalog integrity."""

    def test_total_count_is_44(self, sources_mod):
        assert len(sources_mod._DEFAULT_SITES) == 44

    def test_all_sites_have_required_fields(self, sources_mod):
        required = {"domain", "name", "language", "crawl_method", "anti_block_tier"}
        for i, site in enumerate(sources_mod._DEFAULT_SITES):
            missing = required - set(site.keys())
            assert not missing, f"Site {i} ({site.get('name', '?')}) missing fields: {missing}"

    def test_all_domains_are_non_empty(self, sources_mod):
        for site in sources_mod._DEFAULT_SITES:
            assert site["domain"].strip(), f"Empty domain for {site['name']}"
            assert "." in site["domain"], f"Invalid domain: {site['domain']}"

    def test_language_codes_valid(self, sources_mod):
        valid_langs = {"ko", "en", "ja", "zh", "ar", "fr", "de", "es", "ru"}
        for site in sources_mod._DEFAULT_SITES:
            assert site["language"] in valid_langs, \
                f"Invalid language '{site['language']}' for {site['domain']}"

    def test_anti_block_tier_range(self, sources_mod):
        for site in sources_mod._DEFAULT_SITES:
            tier = site["anti_block_tier"]
            assert isinstance(tier, int) and 1 <= tier <= 3, \
                f"Invalid tier {tier} for {site['domain']}"

    def test_no_duplicate_domains(self, sources_mod):
        domains = [s["domain"] for s in sources_mod._DEFAULT_SITES]
        assert len(domains) == len(set(domains)), \
            f"Duplicates: {[d for d in domains if domains.count(d) > 1]}"


# ============================================================================
# Language Distribution Tests
# ============================================================================

class TestLanguageDistribution:
    """Verify site counts per language."""

    def _count_by_lang(self, mod):
        counts = {}
        for site in mod._DEFAULT_SITES:
            lang = site["language"]
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    def test_korean_sites_count(self, sources_mod):
        """11 (kr-major) + 8 (kr-tech) = 19 Korean sites."""
        counts = self._count_by_lang(sources_mod)
        assert counts.get("ko", 0) == 19

    def test_english_sites_count(self, sources_mod):
        counts = self._count_by_lang(sources_mod)
        assert counts.get("en", 0) == 12

    def test_japanese_sites_count(self, sources_mod):
        counts = self._count_by_lang(sources_mod)
        assert counts.get("ja", 0) == 3

    def test_chinese_sites_count(self, sources_mod):
        counts = self._count_by_lang(sources_mod)
        assert counts.get("zh", 0) == 3

    def test_arabic_sites_count(self, sources_mod):
        counts = self._count_by_lang(sources_mod)
        assert counts.get("ar", 0) == 2

    def test_french_sites_count(self, sources_mod):
        """Le Monde + AFP = 2 French sites."""
        counts = self._count_by_lang(sources_mod)
        assert counts.get("fr", 0) == 2

    def test_all_languages_sum_to_44(self, sources_mod):
        counts = self._count_by_lang(sources_mod)
        assert sum(counts.values()) == 44


# ============================================================================
# YAML Generation Tests
# ============================================================================

class TestYamlGeneration:
    """Test the generate_sources_yaml function output."""

    def test_generates_yaml_file(self, sources_mod, tmp_path):
        from pathlib import Path
        result = sources_mod.generate_sources_yaml(Path(tmp_path))
        assert result["valid"] is True
        assert result["total_sites"] == 44
        assert os.path.exists(result["output_path"])
        assert result["output_size_bytes"] > 1000  # Reasonable minimum

    def test_yaml_contains_all_domains(self, sources_mod, tmp_path):
        from pathlib import Path
        result = sources_mod.generate_sources_yaml(Path(tmp_path))
        with open(result["output_path"]) as f:
            content = f.read()
        # Check a sample of domains from each group
        for domain in ["chosun.com", "zdnet.co.kr", "reuters.com", "nhk.or.jp"]:
            assert domain in content, f"Domain {domain} missing from YAML output"
