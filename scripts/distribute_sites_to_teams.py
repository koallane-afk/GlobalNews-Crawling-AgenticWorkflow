#!/usr/bin/env python3
"""Distribute 44 sites to 4 adapter-dev team members.

Usage: python3 scripts/distribute_sites_to_teams.py --project-dir .

Reads:
  - planning/crawling-strategies.md

Output:
  - planning/team-input/adapters-kr-major.json    (11 sites — Groups A+B+C)
  - planning/team-input/adapters-kr-tech.json     (8 sites — Group D)
  - planning/team-input/adapters-english.json     (12 sites)
  - planning/team-input/adapters-multilingual.json (13 sites — CJK+RTL+European)

Parses the crawling strategies document, splits sites by group,
and includes per-site strategy metadata in each group file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Site group definitions (canonical fallback)
# ---------------------------------------------------------------------------

# Canonical site lists — MUST match adapter agent definitions:
#   kr-major  → .claude/agents/adapter-dev-kr-major.md  (Groups A+B+C = 11 sites)
#   kr-tech   → .claude/agents/adapter-dev-kr-tech.md   (Group D = 8 sites)
#   english   → .claude/agents/adapter-dev-english.md   (12 sites)
#   multilingual → .claude/agents/adapter-dev-multilingual.md (CJK+RTL+EU = 13 sites)
_DEFAULT_GROUPS: dict[str, list[dict[str, str]]] = {
    "kr-major": [
        # Group A — Korean Major Dailies (5)
        {"domain": "chosun.com", "name": "Chosun Ilbo"},
        {"domain": "joongang.co.kr", "name": "JoongAng Ilbo"},
        {"domain": "donga.com", "name": "Dong-A Ilbo"},
        {"domain": "hani.co.kr", "name": "Hankyoreh"},
        {"domain": "yna.co.kr", "name": "Yonhap News"},
        # Group B — Korean Economy (4)
        {"domain": "mk.co.kr", "name": "Maeil Business"},
        {"domain": "hankyung.com", "name": "Korea Economic Daily"},
        {"domain": "fnnews.com", "name": "Financial News"},
        {"domain": "mt.co.kr", "name": "Money Today"},
        # Group C — Korean Niche (2)
        {"domain": "nocutnews.co.kr", "name": "NoCut News"},
        {"domain": "kmib.co.kr", "name": "Kookmin Ilbo"},
    ],
    "kr-tech": [
        # Group D — Korean IT/Tech (8)
        {"domain": "zdnet.co.kr", "name": "ZDNet Korea"},
        {"domain": "itworld.co.kr", "name": "IT World Korea"},
        {"domain": "bloter.net", "name": "Bloter"},
        {"domain": "etnews.com", "name": "Electronic Times"},
        {"domain": "ddaily.co.kr", "name": "Digital Daily"},
        {"domain": "aitimes.com", "name": "AI Times"},
        {"domain": "techm.kr", "name": "TechM"},
        {"domain": "byline.network", "name": "Byline Network"},
    ],
    "english": [
        # API-based
        {"domain": "reuters.com", "name": "Reuters"},
        {"domain": "apnews.com", "name": "AP News"},
        # Paywall-aware
        {"domain": "wsj.com", "name": "Wall Street Journal"},
        {"domain": "nytimes.com", "name": "New York Times"},
        {"domain": "washingtonpost.com", "name": "Washington Post"},
        {"domain": "ft.com", "name": "Financial Times"},
        {"domain": "economist.com", "name": "The Economist"},
        # Standard HTML
        {"domain": "bbc.com", "name": "BBC News"},
        {"domain": "theguardian.com", "name": "The Guardian"},
        {"domain": "cnn.com", "name": "CNN"},
        {"domain": "aljazeera.com", "name": "Al Jazeera English"},
        {"domain": "bloomberg.com", "name": "Bloomberg"},
    ],
    "multilingual": [
        # CJK — Japanese (3)
        {"domain": "nhk.or.jp", "name": "NHK News Web", "language": "ja"},
        {"domain": "asahi.com", "name": "Asahi Shimbun", "language": "ja"},
        {"domain": "nikkei.com", "name": "Nikkei", "language": "ja"},
        # CJK — Chinese (3)
        {"domain": "xinhuanet.com", "name": "Xinhua News", "language": "zh"},
        {"domain": "scmp.com", "name": "South China Morning Post", "language": "zh"},
        {"domain": "caixin.com", "name": "Caixin", "language": "zh"},
        # RTL — Arabic (2)
        {"domain": "aljazeera.net", "name": "Al Jazeera Arabic", "language": "ar"},
        {"domain": "alarabiya.net", "name": "Al Arabiya", "language": "ar"},
        # European (5)
        {"domain": "lemonde.fr", "name": "Le Monde", "language": "fr"},
        {"domain": "spiegel.de", "name": "Der Spiegel", "language": "de"},
        {"domain": "elpais.com", "name": "El Pais", "language": "es"},
        {"domain": "tass.com", "name": "TASS", "language": "ru"},
        {"domain": "afp.com", "name": "Agence France-Presse", "language": "fr"},
    ],
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_SITE_LINE_RE = re.compile(
    r"[-*]\s+\*?\*?([^*\n:]+?)\*?\*?\s*"           # site name
    r"(?:\(([^)]+)\))?"                               # optional (domain)
    r"(?:\s*[-–:]\s*(.+))?$",                         # optional strategy note
    re.MULTILINE,
)

_TABLE_ROW_RE = re.compile(
    r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"            # | col1 | col2 |
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


def _parse_sites_from_strategies(text: str) -> dict[str, list[dict[str, Any]]]:
    """Attempt to parse site groupings from the strategies markdown.

    Returns a dict mapping group-key -> list of site dicts.
    Falls back to _DEFAULT_GROUPS if parsing yields too few sites.
    """
    groups: dict[str, list[dict[str, Any]]] = {
        "kr-major": [],
        "kr-tech": [],
        "english": [],
        "multilingual": [],
    }

    # Heuristic: find sections by heading keywords and collect sites
    group_keywords: dict[str, list[str]] = {
        "kr-major": ["korean major", "kr major", "korean mainstream", "주요 언론",
                      "major korean", "korean news"],
        "kr-tech": ["korean tech", "kr tech", "tech korean", "기술 매체",
                     "tech media", "it media"],
        "english": ["english", "global", "international", "영문",
                     "english-language"],
        "multilingual": ["multilingual", "multi-language", "다국어",
                         "other language", "non-english"],
    }

    headings = list(_HEADING_RE.finditer(text))

    for group_key, keywords in group_keywords.items():
        for idx, heading_match in enumerate(headings):
            title = heading_match.group(2).strip().lower()
            if not any(kw in title for kw in keywords):
                continue

            # Get section text
            start = heading_match.end()
            end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
            section_text = text[start:end]

            # Try to parse sites from bullet lists
            for site_match in _SITE_LINE_RE.finditer(section_text):
                name = site_match.group(1).strip()
                domain = site_match.group(2) or ""
                strategy_note = site_match.group(3) or ""
                if name and len(name) < 80:
                    entry: dict[str, Any] = {"name": name}
                    if domain:
                        entry["domain"] = domain.strip()
                    if strategy_note:
                        entry["strategy"] = strategy_note.strip()
                    groups[group_key].append(entry)

            # Try to parse sites from tables
            for row_match in _TABLE_ROW_RE.finditer(section_text):
                col1 = row_match.group(1).strip()
                col2 = row_match.group(2).strip()
                # Skip table header separators
                if col1.startswith("-") or col1.startswith(":"):
                    continue
                if col1.lower() in ("site", "name", "domain", "source"):
                    continue
                if col1 and len(col1) < 80:
                    entry = {"name": col1}
                    if "." in col2:
                        entry["domain"] = col2
                    else:
                        entry["strategy"] = col2
                    groups[group_key].append(entry)

    # Check if we found enough sites
    total_parsed = sum(len(v) for v in groups.values())
    if total_parsed < 20:
        # Fall back to defaults and try to enrich with strategy notes
        enriched = _enrich_defaults_with_strategies(text)
        return enriched

    return groups


def _enrich_defaults_with_strategies(text: str) -> dict[str, list[dict[str, Any]]]:
    """Use default groups but try to extract per-site strategy notes."""
    result: dict[str, list[dict[str, Any]]] = {}
    text_lower = text.lower()

    for group_key, sites in _DEFAULT_GROUPS.items():
        enriched_sites: list[dict[str, Any]] = []
        for site in sites:
            entry: dict[str, Any] = dict(site)

            # Try to find strategy note near domain mention
            domain = site.get("domain", "")
            name = site.get("name", "")

            strategy_note = _find_strategy_for_site(text, domain, name)
            if strategy_note:
                entry["strategy"] = strategy_note

            enriched_sites.append(entry)
        result[group_key] = enriched_sites

    return result


def _find_strategy_for_site(text: str, domain: str, name: str) -> str:
    """Find a strategy note for a specific site in the text."""
    # Search for lines mentioning the domain or name
    search_terms = [domain, name.lower()] if domain else [name.lower()]
    text_lower = text.lower()

    for term in search_terms:
        if not term:
            continue
        pos = text_lower.find(term.lower())
        if pos == -1:
            continue

        # Extract the surrounding line(s)
        line_start = text.rfind("\n", 0, pos) + 1
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)

        line = text[line_start:line_end].strip()

        # Try to extract strategy part after a separator
        for sep in [":", "–", "—", "->"]:
            sep_pos = line.find(sep, line.lower().find(term.lower()) + len(term))
            if sep_pos != -1:
                note = line[sep_pos + len(sep):].strip()
                if note and len(note) > 5:
                    return note[:200]

    return ""


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def distribute_sites(project_dir: Path) -> dict:
    """Parse strategies and distribute sites to team group files.

    Returns a dict with 'valid', output paths, and diagnostics.
    """
    strategies_path = project_dir / "planning" / "crawling-strategies.md"
    output_dir = project_dir / "planning" / "team-input"

    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Read strategies document
    # ------------------------------------------------------------------
    strategies_text = ""
    if strategies_path.is_file():
        strategies_text = strategies_path.read_text(encoding="utf-8")
    else:
        warnings.append(f"Strategies file not found: {strategies_path}; using defaults")

    # ------------------------------------------------------------------
    # Parse or use defaults
    # ------------------------------------------------------------------
    if strategies_text:
        groups = _parse_sites_from_strategies(strategies_text)
    else:
        groups = _enrich_defaults_with_strategies("")

    # ------------------------------------------------------------------
    # Map group keys to output filenames
    # ------------------------------------------------------------------
    group_files = {
        "kr-major": "adapters-kr-major.json",
        "kr-tech": "adapters-kr-tech.json",
        "english": "adapters-english.json",
        "multilingual": "adapters-multilingual.json",
    }

    # ------------------------------------------------------------------
    # Write output files
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: dict[str, str] = {}
    group_counts: dict[str, int] = {}
    total_sites = 0

    for group_key, filename in group_files.items():
        sites = groups.get(group_key, [])
        out_path = output_dir / filename

        payload = {
            "group": group_key,
            "total_sites": len(sites),
            "sites": sites,
        }

        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        output_paths[group_key] = str(out_path)
        group_counts[group_key] = len(sites)
        total_sites += len(sites)

    result = {
        "valid": True,
        "total_sites": total_sites,
        "group_counts": group_counts,
        "output_paths": output_paths,
        "warnings": warnings,
    }

    # Warn if total does not match expected 44
    if total_sites != 44:
        result["warnings"].append(
            f"Expected 44 sites but distributed {total_sites}."
        )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distribute 44 sites to 4 adapter-dev team members."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = distribute_sites(project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
