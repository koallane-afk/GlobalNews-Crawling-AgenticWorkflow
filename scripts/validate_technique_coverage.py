#!/usr/bin/env python3
"""Technique Coverage Validator — P1 deterministic 56-technique coverage check.

Verifies that a document mentions all 56 analysis techniques from PRD §5.2.
Used after Steps 7, 13-14 to prevent "all 56 techniques mapped" hallucination.

Usage:
    python3 scripts/validate_technique_coverage.py --file planning/analysis-pipeline-design.md --project-dir .

JSON output to stdout. Exit code 0 always.
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# 56 Analysis Techniques — from PRD §5.2
# Grouped by analysis stage
# ---------------------------------------------------------------------------
TECHNIQUES = {
    # Stage 1: Preprocessing
    "language_detection": ["language detection", "langdetect", "language identification"],
    "morphological_analysis": ["morphological analysis", "kiwi", "형태소 분석"],
    "tokenization": ["tokenization", "tokenizer", "토큰화"],
    "stopword_removal": ["stopword removal", "stopword", "불용어"],
    "text_normalization": ["text normalization", "normalization", "정규화"],
    "pos_tagging": ["pos tagging", "part-of-speech", "품사 태깅", "spacy"],

    # Stage 2: Feature Extraction
    "sbert_embedding": ["sbert", "sentence-bert", "sentence embedding", "sentence transformer"],
    "tfidf": ["tf-idf", "tfidf", "term frequency"],
    "ner": ["named entity recognition", "ner", "개체명 인식"],
    "keyword_extraction": ["keyword extraction", "keybert", "keyphrase"],
    "ngram_analysis": ["n-gram", "ngram", "bigram", "trigram"],
    "word_embedding": ["word embedding", "word2vec", "fasttext"],

    # Stage 3: Article-level Analysis
    "sentiment_analysis": ["sentiment analysis", "sentiment", "감정 분석", "opinion mining"],
    "emotion_detection": ["emotion detection", "emotion", "plutchik"],
    "steeps_classification": ["steeps", "social technological economic environmental political"],
    "readability_scoring": ["readability", "flesch", "gunning fog", "smog"],
    "stance_detection": ["stance detection", "stance", "position"],
    "argument_mining": ["argument mining", "claim detection", "argumentation"],
    "headline_analysis": ["headline analysis", "title analysis"],
    "source_credibility": ["source credibility", "credibility scoring"],
    "framing_detection": ["framing detection", "media frame", "frame analysis"],
    "subjectivity": ["subjectivity", "objectivity", "subjective"],

    # Stage 4: Aggregation
    "topic_modeling": ["topic modeling", "bertopic", "lda", "topic model"],
    "hdbscan_clustering": ["hdbscan", "clustering", "density-based"],
    "community_detection": ["community detection", "louvain", "leiden", "modularity"],
    "cross_article_aggregation": ["aggregation", "cross-article", "topic prevalence"],
    "hierarchical_clustering": ["hierarchical clustering", "dendrogram", "agglomerative"],
    "semantic_similarity": ["semantic similarity", "cosine similarity", "sentence similarity"],

    # Stage 5: Time Series
    "stl_decomposition": ["stl", "seasonal trend", "decomposition"],
    "pelt_changepoint": ["pelt", "changepoint", "change point", "ruptures"],
    "kleinberg_burst": ["kleinberg", "burst detection", "burst"],
    "prophet_forecast": ["prophet", "forecast", "time series forecast"],
    "wavelet_analysis": ["wavelet", "cwt", "morlet"],
    "arima": ["arima", "autoregressive", "time series model"],
    "exponential_smoothing": ["exponential smoothing", "ets", "holt-winters"],

    # Stage 6: Cross-Analysis
    "granger_causality": ["granger", "causality", "granger causality"],
    "pcmci": ["pcmci", "causal discovery", "tigramite"],
    "network_analysis": ["network analysis", "graph analysis", "centrality"],
    "narrative_tracking": ["narrative tracking", "narrative", "story tracking"],
    "cross_source_comparison": ["cross-source", "source comparison", "media comparison"],
    "agenda_setting": ["agenda setting", "agenda-setting", "media agenda"],
    "information_cascade": ["information cascade", "cascade", "diffusion"],
    "lead_lag_analysis": ["lead-lag", "lead lag", "temporal precedence"],

    # Stage 7: Signal Classification
    "signal_classification": ["signal classification", "5-layer", "signal hierarchy"],
    "fad_detection": ["fad detection", "fad", "l1 fad", "ephemeral"],
    "short_term_signal": ["short-term signal", "short term", "l2 signal"],
    "mid_term_signal": ["mid-term signal", "mid term", "l3 signal"],
    "long_term_signal": ["long-term signal", "long term", "l4 signal"],
    "singularity_detection": ["singularity", "paradigm shift", "l5 singularity"],
    "novelty_detection": ["novelty detection", "isolation forest", "anomaly detection"],
    "signal_strength": ["signal strength", "confidence interval", "strength scoring"],

    # Stage 8: Storage & Output
    "parquet_output": ["parquet", "apache parquet", "columnar storage"],
    "sqlite_storage": ["sqlite", "sql database", "query interface"],
    "schema_validation": ["schema validation", "data validation", "data integrity"],
    "data_versioning": ["data versioning", "version", "snapshot"],
}


def validate_coverage(project_dir, file_path):
    """Check that file mentions all 56 techniques."""
    result = {
        "valid": True,
        "file": file_path,
        "total_expected": len(TECHNIQUES),
        "found": 0,
        "missing": [],
        "found_techniques": [],
        "warnings": [],
    }

    # Read file
    full_path = os.path.join(project_dir, file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(full_path):
        result["valid"] = False
        result["warnings"].append(f"TC0: File not found: {file_path}")
        return result

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except Exception as e:
        result["valid"] = False
        result["warnings"].append(f"TC0: Cannot read file: {e}")
        return result

    # TC1-TC2: Check each technique
    for tech_id, keywords in TECHNIQUES.items():
        found = False
        for keyword in keywords:
            if keyword.lower() in content:
                found = True
                break
        if found:
            result["found_techniques"].append(tech_id)
        else:
            result["missing"].append(tech_id)

    result["found"] = len(result["found_techniques"])

    # TC3: Missing techniques
    if result["missing"]:
        result["valid"] = False
        result["warnings"].append(f"TC3: {len(result['missing'])} techniques not found in document")

    # TC4: Stage mapping completeness
    stages = {
        "Stage 1": ["language_detection", "morphological_analysis", "tokenization", "stopword_removal", "text_normalization", "pos_tagging"],
        "Stage 2": ["sbert_embedding", "tfidf", "ner", "keyword_extraction", "ngram_analysis", "word_embedding"],
        "Stage 3": ["sentiment_analysis", "emotion_detection", "steeps_classification", "readability_scoring", "stance_detection", "argument_mining", "headline_analysis", "source_credibility", "framing_detection", "subjectivity"],
        "Stage 4": ["topic_modeling", "hdbscan_clustering", "community_detection", "cross_article_aggregation", "hierarchical_clustering", "semantic_similarity"],
        "Stage 5": ["stl_decomposition", "pelt_changepoint", "kleinberg_burst", "prophet_forecast", "wavelet_analysis", "arima", "exponential_smoothing"],
        "Stage 6": ["granger_causality", "pcmci", "network_analysis", "narrative_tracking", "cross_source_comparison", "agenda_setting", "information_cascade", "lead_lag_analysis"],
        "Stage 7": ["signal_classification", "fad_detection", "short_term_signal", "mid_term_signal", "long_term_signal", "singularity_detection", "novelty_detection", "signal_strength"],
        "Stage 8": ["parquet_output", "sqlite_storage", "schema_validation", "data_versioning"],
    }

    stage_coverage = {}
    for stage, techs in stages.items():
        found_in_stage = sum(1 for t in techs if t in result["found_techniques"])
        stage_coverage[stage] = f"{found_in_stage}/{len(techs)}"
        if found_in_stage < len(techs):
            missing_in_stage = [t for t in techs if t not in result["found_techniques"]]
            result["warnings"].append(f"TC4: {stage} missing: {missing_in_stage}")

    result["stage_coverage"] = stage_coverage
    result["coverage_pct"] = round(result["found"] / result["total_expected"] * 100, 1)

    return result


def main():
    parser = argparse.ArgumentParser(description="Technique Coverage Validator — P1")
    parser.add_argument("--file", required=True, help="Document file to check")
    parser.add_argument("--project-dir", required=True, help="Project root directory")
    args = parser.parse_args()

    result = validate_coverage(args.project_dir, args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
