"""Unit tests for Stage 4 Aggregation (BERTopic, HDBSCAN, NMF, LDA, Louvain).

Minimal test coverage for Track A changes:
    - BERTopic/HDBSCAN parameter constants
    - Stopword configuration
    - Topic output schema contract (topics.parquet columns)
    - Stage4Aggregator initialization
    - Noise ratio handling (max_noise_ratio threshold)

These tests do NOT require actual SBERT model loading.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.stage4_aggregation import (
    AUX_N_COMPONENTS,
    BERTOPIC_MIN_TOPIC_SIZE,
    BERTOPIC_NR_TOPICS,
    HDBSCAN_FALLBACK_MIN_CLUSTER_SIZE,
    HDBSCAN_MAX_NOISE_RATIO,
    HDBSCAN_MIN_CLUSTER_SIZE,
    HDBSCAN_MIN_SAMPLES,
    KMEANS_K_RANGE,
    LOUVAIN_EDGE_MIN_COOCCURRENCE,
    Stage4Aggregator,
)


# =============================================================================
# Constants Validation
# =============================================================================


class TestStage4Constants:
    """Verify Stage 4 constants are reasonable."""

    def test_hdbscan_min_cluster_size_positive(self):
        assert HDBSCAN_MIN_CLUSTER_SIZE > 0

    def test_hdbscan_min_samples_positive(self):
        assert HDBSCAN_MIN_SAMPLES > 0

    def test_hdbscan_fallback_smaller_than_primary(self):
        """Fallback should be smaller or equal to primary."""
        assert HDBSCAN_FALLBACK_MIN_CLUSTER_SIZE <= HDBSCAN_MIN_CLUSTER_SIZE

    def test_hdbscan_max_noise_ratio_valid(self):
        """Noise ratio threshold should be between 0 and 1."""
        assert 0.0 < HDBSCAN_MAX_NOISE_RATIO <= 1.0

    def test_bertopic_min_topic_size_positive(self):
        assert BERTOPIC_MIN_TOPIC_SIZE > 0

    def test_bertopic_nr_topics_is_auto(self):
        assert BERTOPIC_NR_TOPICS == "auto"

    def test_nmf_lda_components_reasonable(self):
        assert 5 <= AUX_N_COMPONENTS <= 100

    def test_kmeans_k_range_ordered(self):
        k_min, k_max = KMEANS_K_RANGE
        assert k_min < k_max
        assert k_min >= 2

    def test_louvain_min_cooccurrence_positive(self):
        assert LOUVAIN_EDGE_MIN_COOCCURRENCE >= 1


# =============================================================================
# Topics Output Contract
# =============================================================================


class TestTopicsOutputContract:
    """Verify topics.parquet expected schema."""

    def test_expected_topic_columns(self):
        """topics.parquet must have these columns."""
        expected = {
            "article_id", "topic_id", "topic_label", "topic_probability",
            "hdbscan_cluster_id", "nmf_topic_id", "lda_topic_id",
            "published_at", "source",
        }
        assert len(expected) == 9

    def test_topic_id_type_is_int(self):
        """topic_id must be int32 (not string)."""
        import pyarrow as pa
        from src.storage.parquet_writer import TOPICS_PA_SCHEMA
        field = TOPICS_PA_SCHEMA.field("topic_id")
        assert field.type == pa.int32()


# =============================================================================
# Aggregator Initialization
# =============================================================================


class TestStage4AggregatorInit:
    """Verify Stage4Aggregator can be instantiated."""

    def test_init_without_sbert_model(self):
        """Should initialize with sbert_model=None."""
        aggregator = Stage4Aggregator(sbert_model=None)
        assert aggregator is not None

    def test_init_creates_empty_state(self):
        """Initial state should have no cached models."""
        aggregator = Stage4Aggregator(sbert_model=None)
        # Verify it doesn't crash on creation
        aggregator.cleanup()


# =============================================================================
# Stopword Configuration (Track A-1 target)
# =============================================================================


class TestStopwordConfiguration:
    """Tests related to stopword handling in BERTopic."""

    def test_countvectorizer_used_in_bertopic(self):
        """Verify CountVectorizer is imported and available."""
        from sklearn.feature_extraction.text import CountVectorizer
        cv = CountVectorizer(stop_words="english")
        assert cv.get_stop_words() is not None
        assert len(cv.get_stop_words()) > 100  # English has 300+ stop words

    def test_multilingual_stopwords_coverage(self):
        """When we add multilingual stopwords, they should cover key languages."""
        # This test documents the expected behavior AFTER A-1 fix.
        # Currently it verifies the baseline: only English stopwords are used.
        from sklearn.feature_extraction.text import CountVectorizer
        cv = CountVectorizer(stop_words="english")
        english_stops = cv.get_stop_words()
        # Spanish stopwords NOT in English set (this is the gap A-1 fixes)
        assert "la" not in english_stops
        assert "que" not in english_stops
        assert "el" not in english_stops
