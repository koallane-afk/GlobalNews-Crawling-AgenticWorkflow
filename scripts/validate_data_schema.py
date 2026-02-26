#!/usr/bin/env python3
"""Data Schema Validator — P1 deterministic schema completeness check.

Verifies Parquet/config schemas match PRD §7.1 requirements.
Used after Steps 5, 9 to prevent schema hallucination.

Usage:
    python3 scripts/validate_data_schema.py --step 5 --project-dir .
    python3 scripts/validate_data_schema.py --step 9 --check-config --project-dir .

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# PRD §7.1 Required Columns per Parquet Table
# ---------------------------------------------------------------------------

ARTICLES_COLUMNS = {
    "article_id": "string",
    "url": "string",
    "title": "string",
    "body": "string",
    "published_date": "datetime",
    "author": "string",
    "source_domain": "string",
    "source_name": "string",
    "language": "string",
    "section": "string",
    "word_count": "integer",
    "crawl_timestamp": "datetime",
}

ANALYSIS_COLUMNS = {
    "article_id": "string",
    "sentiment_score": "float",
    "sentiment_label": "string",
    "emotion_primary": "string",
    "emotion_scores": "json",
    "steeps_category": "string",
    "readability_score": "float",
    "keywords": "json",
    "entities": "json",
    "topic_id": "integer",
}

SIGNALS_COLUMNS = {
    "signal_id": "string",
    "topic_id": "integer",
    "signal_layer": "string",
    "signal_strength": "float",
    "confidence": "float",
    "first_detected": "datetime",
    "last_updated": "datetime",
    "article_count": "integer",
    "source_count": "integer",
    "description": "string",
}

TOPICS_COLUMNS = {
    "topic_id": "integer",
    "topic_label": "string",
    "keywords": "json",
    "article_count": "integer",
    "source_diversity": "float",
    "avg_sentiment": "float",
    "first_seen": "datetime",
    "last_seen": "datetime",
}

PRD_SCHEMAS = {
    "articles": ARTICLES_COLUMNS,
    "analysis": ANALYSIS_COLUMNS,
    "signals": SIGNALS_COLUMNS,
    "topics": TOPICS_COLUMNS,
}

# ---------------------------------------------------------------------------
# Config structure requirements
# ---------------------------------------------------------------------------

SOURCES_YAML_REQUIRED_FIELDS = [
    "sites",  # list of site configs
]

SITE_CONFIG_REQUIRED_FIELDS = [
    "domain", "name", "language", "crawl_method",
]

PIPELINE_YAML_REQUIRED_FIELDS = [
    "stages",  # list of stage configs
]

STAGE_CONFIG_REQUIRED_FIELDS = [
    "name", "input", "output",
]


def _extract_schema_from_doc(content, table_name):
    """Extract column definitions from architecture document for a given table."""
    columns = {}
    # Look for table definition section
    pattern = rf'(?:#{1,4}\s*{re.escape(table_name)}|{re.escape(table_name)}\s*(?:table|schema))'
    match = re.search(pattern, content, re.IGNORECASE)
    if not match:
        return None

    # Extract region after the match (next 50 lines or until next heading)
    start = match.end()
    region = content[start:start + 3000]

    # Look for column definitions in tables or lists
    # Table format: | column_name | type | ...
    for m in re.finditer(r'\|\s*`?(\w+)`?\s*\|\s*`?(\w+)`?\s*\|', region):
        col_name = m.group(1).lower()
        col_type = m.group(2).lower()
        if col_name not in ("column", "field", "name", "---", ""):
            columns[col_name] = col_type

    # List format: - column_name: type
    for m in re.finditer(r'-\s*`?(\w+)`?\s*(?::|—)\s*(\w+)', region):
        col_name = m.group(1).lower()
        col_type = m.group(2).lower()
        if col_name not in ("column", "field", "name"):
            columns[col_name] = col_type

    return columns if columns else None


def _check_config_files(project_dir):
    """Validate sources.yaml and pipeline.yaml structure."""
    warnings = []

    # sources.yaml
    sources_path = os.path.join(project_dir, "config", "sources.yaml")
    if not os.path.exists(sources_path):
        warnings.append("DS_CFG1: config/sources.yaml not found")
    else:
        try:
            import yaml
            with open(sources_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                sites = data.get("sites", [])
                if not sites:
                    warnings.append("DS_CFG2: sources.yaml has no 'sites' section")
                elif isinstance(sites, list):
                    for i, site in enumerate(sites[:5]):  # Check first 5
                        if isinstance(site, dict):
                            for field in SITE_CONFIG_REQUIRED_FIELDS:
                                if field not in site:
                                    warnings.append(f"DS_CFG3: sites[{i}] missing field: {field}")
                    if len(sites) < 44:
                        warnings.append(f"DS_CFG4: sources.yaml has {len(sites)} sites (expected 44)")
        except Exception as e:
            warnings.append(f"DS_CFG1b: sources.yaml parse error: {e}")

    # pipeline.yaml
    pipeline_path = os.path.join(project_dir, "config", "pipeline.yaml")
    if not os.path.exists(pipeline_path):
        warnings.append("DS_CFG5: config/pipeline.yaml not found")
    else:
        try:
            import yaml
            with open(pipeline_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                stages = data.get("stages", [])
                if not stages:
                    warnings.append("DS_CFG6: pipeline.yaml has no 'stages' section")
                elif isinstance(stages, list) and len(stages) < 8:
                    warnings.append(f"DS_CFG7: pipeline.yaml has {len(stages)} stages (expected 8)")
        except Exception as e:
            warnings.append(f"DS_CFG5b: pipeline.yaml parse error: {e}")

    return warnings


def validate_schema(project_dir, step_num, check_config=False):
    """Validate schema definitions against PRD requirements."""
    result = {
        "valid": True,
        "step": step_num,
        "tables": {},
        "warnings": [],
    }

    # Find the architecture document
    if step_num == 5:
        doc_paths = [
            os.path.join(project_dir, "planning", "architecture-blueprint.md"),
        ]
    elif step_num == 9:
        doc_paths = [
            os.path.join(project_dir, "src", "storage", "parquet_writer.py"),
            os.path.join(project_dir, "src", "storage", "schema.py"),
            os.path.join(project_dir, "planning", "architecture-blueprint.md"),
        ]
    else:
        doc_paths = []

    # Read available documents
    content = ""
    for dp in doc_paths:
        if os.path.exists(dp):
            try:
                with open(dp, "r", encoding="utf-8") as f:
                    content += "\n" + f.read()
            except Exception:
                pass

    if not content:
        result["valid"] = False
        result["warnings"].append("DS0: No schema document found")
        return result

    # DS1-DS3: Check each PRD table
    for table_name, required_cols in PRD_SCHEMAS.items():
        table_result = {"required": list(required_cols.keys()), "found": [], "missing": []}

        # Extract schema from document
        found_cols = _extract_schema_from_doc(content, table_name)
        if found_cols is None:
            # Try searching by column names in content
            for col in required_cols:
                if col.lower() in content.lower():
                    table_result["found"].append(col)
                else:
                    table_result["missing"].append(col)
        else:
            for col in required_cols:
                if col in found_cols:
                    table_result["found"].append(col)
                else:
                    table_result["missing"].append(col)

        result["tables"][table_name] = table_result

        if table_result["missing"]:
            result["warnings"].append(
                f"DS3: {table_name} missing columns: {table_result['missing']}"
            )

    # DS4: Config file check
    if check_config:
        config_warnings = _check_config_files(project_dir)
        result["warnings"].extend(config_warnings)

    if result["warnings"]:
        result["valid"] = False

    return result


def main():
    parser = argparse.ArgumentParser(description="Data Schema Validator — P1")
    parser.add_argument("--step", type=int, required=True, help="Step number (5 or 9)")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    parser.add_argument("--check-config", action="store_true", help="Also validate config files")
    args = parser.parse_args()

    result = validate_schema(args.project_dir, args.step, args.check_config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
