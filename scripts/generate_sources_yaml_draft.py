#!/usr/bin/env python3
"""Generate sources.yaml draft from site reconnaissance.

Usage: python3 scripts/generate_sources_yaml_draft.py --project-dir .

Reads:
  - research/site-reconnaissance.md  (Step 1 output)

Output:
  - config/sources.yaml (draft)

Parses the site reconnaissance output and generates a YAML config per
site with: domain, name, language, crawl_method, rss_url, sitemap_url,
rate_limit, ua_rotation, anti_block_tier.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# PyYAML import (graceful fallback)
# ---------------------------------------------------------------------------

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ---------------------------------------------------------------------------
# Constants — default site catalog
# ---------------------------------------------------------------------------

# Canonical 44-site catalog — MUST match adapter agent definitions:
#   .claude/agents/adapter-dev-kr-major.md      (11 sites)
#   .claude/agents/adapter-dev-kr-tech.md       (8 sites)
#   .claude/agents/adapter-dev-english.md       (12 sites)
#   .claude/agents/adapter-dev-multilingual.md  (13 sites)
_DEFAULT_SITES: list[dict[str, Any]] = [
    # Korean major — Group A: Major Dailies (5)
    {"domain": "chosun.com", "name": "Chosun Ilbo", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "joongang.co.kr", "name": "JoongAng Ilbo", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "donga.com", "name": "Dong-A Ilbo", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "hani.co.kr", "name": "Hankyoreh", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "yna.co.kr", "name": "Yonhap News", "language": "ko", "crawl_method": "rss+api", "anti_block_tier": 2},
    # Korean major — Group B: Economy (4)
    {"domain": "mk.co.kr", "name": "Maeil Business", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "hankyung.com", "name": "Korea Economic Daily", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "fnnews.com", "name": "Financial News", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "mt.co.kr", "name": "Money Today", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    # Korean major — Group C: Niche (2)
    {"domain": "nocutnews.co.kr", "name": "NoCut News", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "kmib.co.kr", "name": "Kookmin Ilbo", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    # Korean tech — Group D (8)
    {"domain": "zdnet.co.kr", "name": "ZDNet Korea", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "itworld.co.kr", "name": "IT World Korea", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "bloter.net", "name": "Bloter", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "etnews.com", "name": "Electronic Times", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "ddaily.co.kr", "name": "Digital Daily", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "aitimes.com", "name": "AI Times", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    {"domain": "techm.kr", "name": "TechM", "language": "ko", "crawl_method": "html", "anti_block_tier": 1},
    {"domain": "byline.network", "name": "Byline Network", "language": "ko", "crawl_method": "rss+html", "anti_block_tier": 1},
    # English (12)
    {"domain": "reuters.com", "name": "Reuters", "language": "en", "crawl_method": "rss+api", "anti_block_tier": 3},
    {"domain": "apnews.com", "name": "AP News", "language": "en", "crawl_method": "rss+api", "anti_block_tier": 2},
    {"domain": "wsj.com", "name": "Wall Street Journal", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "nytimes.com", "name": "New York Times", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "washingtonpost.com", "name": "Washington Post", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "ft.com", "name": "Financial Times", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "economist.com", "name": "The Economist", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "bbc.com", "name": "BBC News", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "theguardian.com", "name": "The Guardian", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "cnn.com", "name": "CNN", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    {"domain": "aljazeera.com", "name": "Al Jazeera English", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "bloomberg.com", "name": "Bloomberg", "language": "en", "crawl_method": "rss+html", "anti_block_tier": 3},
    # Multilingual — CJK Japanese (3)
    {"domain": "nhk.or.jp", "name": "NHK News Web", "language": "ja", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "asahi.com", "name": "Asahi Shimbun", "language": "ja", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "nikkei.com", "name": "Nikkei", "language": "ja", "crawl_method": "rss+html", "anti_block_tier": 3},
    # Multilingual — CJK Chinese (3)
    {"domain": "xinhuanet.com", "name": "Xinhua News", "language": "zh", "crawl_method": "html", "anti_block_tier": 2},
    {"domain": "scmp.com", "name": "South China Morning Post", "language": "zh", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "caixin.com", "name": "Caixin", "language": "zh", "crawl_method": "html", "anti_block_tier": 2},
    # Multilingual — RTL Arabic (2)
    {"domain": "aljazeera.net", "name": "Al Jazeera Arabic", "language": "ar", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "alarabiya.net", "name": "Al Arabiya", "language": "ar", "crawl_method": "rss+html", "anti_block_tier": 2},
    # Multilingual — European (5)
    {"domain": "lemonde.fr", "name": "Le Monde", "language": "fr", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "spiegel.de", "name": "Der Spiegel", "language": "de", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "elpais.com", "name": "El Pais", "language": "es", "crawl_method": "rss+html", "anti_block_tier": 2},
    {"domain": "tass.com", "name": "TASS", "language": "ru", "crawl_method": "html", "anti_block_tier": 2},
    {"domain": "afp.com", "name": "Agence France-Presse", "language": "fr", "crawl_method": "rss+html", "anti_block_tier": 2},
]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)
_URL_RE = re.compile(r"https?://[^\s)\"'>]+")
_DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9][-a-z0-9]*\.[a-z.]+)", re.IGNORECASE)


def _parse_reconnaissance(text: str) -> list[dict[str, Any]]:
    """Attempt to parse site data from reconnaissance markdown.

    Tries to extract per-site blocks and enrich the default catalog.
    """
    if not text.strip():
        return _DEFAULT_SITES

    # Build a lookup from the default catalog
    defaults_by_domain = {s["domain"]: dict(s) for s in _DEFAULT_SITES}
    enriched: dict[str, dict[str, Any]] = {}

    # Strategy: find domain mentions and extract nearby metadata
    for domain, site_defaults in defaults_by_domain.items():
        entry = dict(site_defaults)

        # Search for domain in text
        domain_pattern = re.escape(domain)
        matches = list(re.finditer(domain_pattern, text, re.IGNORECASE))
        if not matches:
            enriched[domain] = entry
            continue

        # Use the first mention's surrounding context (500 chars each way)
        pos = matches[0].start()
        context_start = max(0, pos - 500)
        context_end = min(len(text), pos + 500)
        context = text[context_start:context_end]
        context_lower = context.lower()

        # Extract RSS URL
        rss_match = re.search(r"rss[:\s]*\*?\*?\s*(https?://[^\s)\"'>]+)", context, re.IGNORECASE)
        if rss_match:
            entry["rss_url"] = rss_match.group(1).strip()

        # Extract sitemap URL
        sitemap_match = re.search(r"sitemap[:\s]*\*?\*?\s*(https?://[^\s)\"'>]+)", context, re.IGNORECASE)
        if sitemap_match:
            entry["sitemap_url"] = sitemap_match.group(1).strip()

        # Extract rate limit
        rate_match = re.search(r"rate[_\s-]*limit[:\s]*(\d+(?:\.\d+)?)\s*(?:req(?:uest)?s?)?/?\s*(?:s|sec|second|min|minute)?", context, re.IGNORECASE)
        if rate_match:
            entry["rate_limit"] = f"{rate_match.group(1)}/s"

        # Detect crawl method overrides
        if "api" in context_lower and ("endpoint" in context_lower or "json" in context_lower):
            if "rss" in context_lower:
                entry["crawl_method"] = "rss+api"
            else:
                entry["crawl_method"] = "api"
        elif "headless" in context_lower or "javascript" in context_lower or "spa" in context_lower:
            entry["crawl_method"] = "headless"
        elif "sitemap" in context_lower and "rss" not in context_lower:
            entry["crawl_method"] = "sitemap+html"

        # Detect UA rotation need
        if any(kw in context_lower for kw in ["user-agent", "ua rotation", "bot detection", "cloudflare"]):
            entry["ua_rotation"] = True
        else:
            entry["ua_rotation"] = False

        # Detect anti-block tier from context clues
        if any(kw in context_lower for kw in ["cloudflare", "captcha", "paywall", "403", "rate limit aggressive"]):
            entry["anti_block_tier"] = max(entry.get("anti_block_tier", 1), 3)
        elif any(kw in context_lower for kw in ["moderate protection", "cookie required", "session"]):
            entry["anti_block_tier"] = max(entry.get("anti_block_tier", 1), 2)

        enriched[domain] = entry

    # Add any defaults not found
    for domain, site_defaults in defaults_by_domain.items():
        if domain not in enriched:
            enriched[domain] = site_defaults

    return list(enriched.values())


def _build_yaml_string(sites: list[dict[str, Any]]) -> str:
    """Build a YAML string from sites list.

    Uses PyYAML if available; otherwise constructs YAML manually for
    deterministic output without external dependencies.
    """
    if _HAS_YAML:
        doc = {
            "_meta": {
                "version": "1.0.0-draft",
                "generated_by": "generate_sources_yaml_draft.py",
                "description": "News sources configuration — auto-generated draft from site reconnaissance",
                "total_sites": len(sites),
            },
            "sources": sites,
        }
        return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Manual YAML construction
    lines: list[str] = []
    lines.append("# News Sources Configuration (Draft)")
    lines.append("# Auto-generated by generate_sources_yaml_draft.py")
    lines.append(f"# Total sites: {len(sites)}")
    lines.append("")
    lines.append("_meta:")
    lines.append("  version: 1.0.0-draft")
    lines.append("  generated_by: generate_sources_yaml_draft.py")
    lines.append("  description: News sources configuration — auto-generated draft from site reconnaissance")
    lines.append(f"  total_sites: {len(sites)}")
    lines.append("")
    lines.append("sources:")

    for site in sites:
        lines.append(f"  - domain: {site['domain']}")
        lines.append(f"    name: \"{site['name']}\"")
        lines.append(f"    language: {site.get('language', 'en')}")
        lines.append(f"    crawl_method: {site.get('crawl_method', 'rss+html')}")

        if "rss_url" in site:
            lines.append(f"    rss_url: {site['rss_url']}")
        if "sitemap_url" in site:
            lines.append(f"    sitemap_url: {site['sitemap_url']}")

        rate_limit = site.get("rate_limit", "1/s")
        lines.append(f"    rate_limit: \"{rate_limit}\"")

        ua_rotation = site.get("ua_rotation", False)
        lines.append(f"    ua_rotation: {'true' if ua_rotation else 'false'}")

        anti_block_tier = site.get("anti_block_tier", 1)
        lines.append(f"    anti_block_tier: {anti_block_tier}")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def generate_sources_yaml(project_dir: Path) -> dict:
    """Generate sources.yaml draft from reconnaissance data.

    Returns a dict with 'valid', 'output_path', and diagnostics.
    """
    recon_path = project_dir / "research" / "site-reconnaissance.md"
    output_dir = project_dir / "config"
    output_path = output_dir / "sources.yaml"

    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Read reconnaissance
    # ------------------------------------------------------------------
    recon_text = ""
    if recon_path.is_file():
        recon_text = recon_path.read_text(encoding="utf-8")
    else:
        warnings.append(f"Reconnaissance not found: {recon_path}; using default catalog")

    # ------------------------------------------------------------------
    # Parse and enrich sites
    # ------------------------------------------------------------------
    sites = _parse_reconnaissance(recon_text)

    # ------------------------------------------------------------------
    # Generate YAML
    # ------------------------------------------------------------------
    yaml_content = _build_yaml_string(sites)

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Compute stats
    # ------------------------------------------------------------------
    languages = {}
    methods = {}
    tiers = {1: 0, 2: 0, 3: 0}

    for site in sites:
        lang = site.get("language", "unknown")
        languages[lang] = languages.get(lang, 0) + 1

        method = site.get("crawl_method", "unknown")
        methods[method] = methods.get(method, 0) + 1

        tier = site.get("anti_block_tier", 1)
        if tier in tiers:
            tiers[tier] += 1

    result = {
        "valid": True,
        "output_path": str(output_path),
        "total_sites": len(sites),
        "languages": languages,
        "crawl_methods": methods,
        "anti_block_tiers": tiers,
        "output_size_bytes": len(yaml_content.encode("utf-8")),
        "has_yaml_lib": _HAS_YAML,
        "warnings": warnings,
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sources.yaml draft from site reconnaissance."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = generate_sources_yaml(project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
