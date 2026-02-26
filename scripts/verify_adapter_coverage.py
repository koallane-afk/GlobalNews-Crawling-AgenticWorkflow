#!/usr/bin/env python3
"""Verify adapter coverage against sources.yaml.

Usage: python3 scripts/verify_adapter_coverage.py --project-dir .

Reads:
  - config/sources.yaml
  - src/crawling/adapters/  (adapter files)

Output:
  - JSON to stdout

Reads sources.yaml for 44 site domains, scans src/crawling/adapters/
for adapter files, checks adapter registry (__init__.py) for domain
mappings, and reports covered/missing/extra domains.
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
# Helpers
# ---------------------------------------------------------------------------

_DOMAIN_RE = re.compile(r"""['"]([a-z0-9][-a-z0-9]*\.[a-z.]+)['"]""", re.IGNORECASE)
_CLASS_RE = re.compile(r"class\s+(\w+Adapter)\b", re.IGNORECASE)
_REGISTRY_RE = re.compile(
    r"""['"]([a-z0-9][-a-z0-9]*\.[a-z.]+)['"]"""
    r"""\s*:\s*(\w+)""",
    re.IGNORECASE,
)


def _load_sources_yaml(path: Path) -> list[str]:
    """Load source domains from sources.yaml.

    Returns a list of domain strings.
    """
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")

    if _HAS_YAML:
        try:
            doc = yaml.safe_load(text)
            if isinstance(doc, dict) and "sources" in doc:
                sources = doc["sources"]
                if isinstance(sources, list):
                    domains = []
                    for entry in sources:
                        if isinstance(entry, dict) and "domain" in entry:
                            domains.append(entry["domain"].strip().lower())
                    return domains
        except yaml.YAMLError:
            pass

    # Fallback: regex extraction
    domains: list[str] = []
    for match in re.finditer(r"domain:\s*(\S+)", text):
        domain = match.group(1).strip().strip("'\"").lower()
        if "." in domain:
            domains.append(domain)

    return domains


def _scan_adapter_files(adapters_dir: Path) -> dict[str, dict[str, Any]]:
    """Scan adapter directory for .py files and extract domain mappings.

    Returns a dict of adapter_file -> {classes, domains}.
    """
    adapters: dict[str, dict[str, Any]] = {}

    if not adapters_dir.is_dir():
        return adapters

    for py_file in sorted(adapters_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue

        text = py_file.read_text(encoding="utf-8")

        # Extract adapter classes
        classes = _CLASS_RE.findall(text)

        # Extract domain references
        domains = []
        for m in _DOMAIN_RE.finditer(text):
            d = m.group(1).lower()
            if "." in d and len(d) > 3:
                domains.append(d)

        # Also check for domain in filename (e.g., chosun_adapter.py -> chosun.com)
        stem = py_file.stem.replace("_adapter", "").replace("_", ".")

        adapters[py_file.name] = {
            "classes": classes,
            "domains": list(set(domains)),
            "stem": stem,
        }

    return adapters


def _parse_registry(init_path: Path) -> dict[str, str]:
    """Parse __init__.py for domain -> adapter class mappings."""
    registry: dict[str, str] = {}

    if not init_path.is_file():
        return registry

    text = init_path.read_text(encoding="utf-8")

    # Look for registry dict patterns
    for m in _REGISTRY_RE.finditer(text):
        domain = m.group(1).lower()
        adapter_class = m.group(2)
        registry[domain] = adapter_class

    return registry


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def verify_coverage(project_dir: Path) -> dict:
    """Cross-check adapter files against sources.yaml.

    Returns a dict with coverage analysis.
    """
    sources_path = project_dir / "config" / "sources.yaml"
    adapters_dir = project_dir / "src" / "crawling" / "adapters"
    init_path = adapters_dir / "__init__.py"

    warnings: list[str] = []
    errors: list[str] = []

    # ------------------------------------------------------------------
    # Load expected domains from sources.yaml
    # ------------------------------------------------------------------
    expected_domains = _load_sources_yaml(sources_path)
    if not expected_domains:
        errors.append(f"No domains found in {sources_path}")

    expected_set = set(expected_domains)

    # ------------------------------------------------------------------
    # Scan adapter files
    # ------------------------------------------------------------------
    adapter_files = _scan_adapter_files(adapters_dir)
    if not adapter_files and adapters_dir.is_dir():
        warnings.append("No adapter .py files found (excluding __init__.py)")
    elif not adapters_dir.is_dir():
        warnings.append(f"Adapters directory not found: {adapters_dir}")

    # Collect all domains covered by adapter files
    covered_by_files: set[str] = set()
    for info in adapter_files.values():
        covered_by_files.update(info["domains"])

    # ------------------------------------------------------------------
    # Parse registry
    # ------------------------------------------------------------------
    registry = _parse_registry(init_path)
    if not registry and init_path.is_file():
        warnings.append("__init__.py exists but no domain mappings found")
    elif not init_path.is_file():
        warnings.append(f"Registry __init__.py not found: {init_path}")

    registered_domains = set(registry.keys())

    # ------------------------------------------------------------------
    # Compute coverage
    # ------------------------------------------------------------------
    # A domain is "covered" if it appears in either adapter files or registry
    all_covered = covered_by_files | registered_domains

    covered = expected_set & all_covered
    missing = expected_set - all_covered
    extra = all_covered - expected_set

    # Domains in files but not in registry
    file_only = covered_by_files - registered_domains
    # Domains in registry but not in files
    registry_only = registered_domains - covered_by_files

    total_expected = len(expected_set)
    total_covered = len(covered)
    coverage_pct = (total_covered / total_expected * 100) if total_expected > 0 else 0.0

    result = {
        "valid": len(errors) == 0,
        "summary": {
            "expected_domains": total_expected,
            "covered_domains": total_covered,
            "missing_domains": len(missing),
            "extra_domains": len(extra),
            "coverage_percent": round(coverage_pct, 1),
        },
        "covered": sorted(covered),
        "missing": sorted(missing),
        "extra": sorted(extra),
        "file_only_not_registered": sorted(file_only),
        "registry_only_no_file": sorted(registry_only),
        "adapter_files": {
            name: {
                "classes": info["classes"],
                "domains": info["domains"],
            }
            for name, info in adapter_files.items()
        },
        "registry_entries": len(registry),
        "warnings": warnings,
        "errors": errors,
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify adapter coverage against sources.yaml."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project root directory.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = verify_coverage(project_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit with error if no domains found at all
    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
