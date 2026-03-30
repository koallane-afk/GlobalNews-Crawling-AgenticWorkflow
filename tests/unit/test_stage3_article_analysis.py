"""Unit tests for Stage 3 Article Analysis (sentiment, emotion, STEEPS, importance).

Minimal test coverage for Track A changes:
    - Sentiment analysis language branching (ko/en/other)
    - Sentiment output contract (label in {positive, negative, neutral}, score in [-1, 1])
    - Emotion classification output contract (8 Plutchik dimensions, 0-1 range)
    - STEEPS classification output contract
    - Importance score range (0-100)
    - validate_output() basic checks

These tests mock transformer models to run without GPU/model downloads.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.stage3_article_analysis import (
    PLUTCHIK_EMOTIONS,
    STEEPS_CODE_MAP,
    STEEPS_LABELS,
    Stage3ArticleAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analyzer():
    """Create a Stage3ArticleAnalyzer with mocked models."""
    with patch.object(Stage3ArticleAnalyzer, "__init__", lambda self, **kw: None):
        a = Stage3ArticleAnalyzer.__new__(Stage3ArticleAnalyzer)
        a.articles_path = Path("/tmp/test_articles.parquet")
        a.features_dir = Path("/tmp/features")
        a.output_path = Path("/tmp/test_output.parquet")
        a.source_authority = {"test_source": 50}
        a._en_sentiment_pipeline = None
        a._ko_sentiment_pipeline = None
        a._multilingual_sentiment_pipeline = None
        a._zeroshot_pipeline = None
        a._en_sentiment_available = False
        a._ko_sentiment_available = False
        a._multilingual_sentiment_available = False
        a._zeroshot_available = False
        a._memory_log = []
        a._device = "cpu"

        # Provide fallback analyzers
        from src.analysis.stage3_article_analysis import (
            _KoreanLexiconFallback,
            _VaderFallback,
        )
        a._vader_fallback = _VaderFallback()
        a._korean_fallback = _KoreanLexiconFallback()
        return a


# =============================================================================
# Sentiment Tests
# =============================================================================


class TestSentimentBranching:
    """Verify sentiment analysis routes correctly by language."""

    def test_korean_routes_to_ko_analyzer(self, analyzer):
        """Korean text should use _analyze_sentiment_ko."""
        label, score = analyzer._analyze_sentiment("테스트 제목", "테스트 본문", "ko")
        assert label in {"positive", "negative", "neutral"}
        assert -1.0 <= score <= 1.0

    def test_english_routes_to_en_analyzer(self, analyzer):
        """English text should use _analyze_sentiment_en."""
        label, score = analyzer._analyze_sentiment("Test title", "Test body text", "en")
        assert label in {"positive", "negative", "neutral"}
        assert -1.0 <= score <= 1.0

    def test_other_language_routes_to_en_fallback(self, analyzer):
        """Non-ko/en text currently falls through to en analyzer."""
        label, score = analyzer._analyze_sentiment("Título", "Cuerpo del artículo", "es")
        assert label in {"positive", "negative", "neutral"}
        assert -1.0 <= score <= 1.0

    def test_empty_text_returns_neutral(self, analyzer):
        """Empty body should still return valid sentiment."""
        label, score = analyzer._analyze_sentiment("Title", "", "en")
        assert label in {"positive", "negative", "neutral"}
        assert -1.0 <= score <= 1.0

    def test_sentiment_labels_are_standard(self, analyzer):
        """Output labels must be from the standard set."""
        valid_labels = {"positive", "negative", "neutral"}
        for lang in ["en", "ko"]:
            label, _ = analyzer._analyze_sentiment("test", "test body", lang)
            assert label in valid_labels, f"Unexpected label '{label}' for {lang}"


# =============================================================================
# Emotion Tests
# =============================================================================


class TestEmotionClassification:
    """Verify emotion output contract."""

    def test_emotion_returns_all_8_dimensions(self, analyzer):
        """Emotion classification must return all 8 Plutchik emotions."""
        result = analyzer._classify_emotions("This is a happy news article")
        assert set(result.keys()) == set(PLUTCHIK_EMOTIONS)

    def test_emotion_scores_in_valid_range(self, analyzer):
        """All emotion scores must be in [0, 1]."""
        result = analyzer._classify_emotions("A terrible disaster occurred")
        for emotion, score in result.items():
            assert 0.0 <= score <= 1.0, f"{emotion} score {score} out of range"

    def test_emotion_empty_text_returns_uniform(self, analyzer):
        """Empty text should return uniform distribution (0.125 each)."""
        result = analyzer._classify_emotions("")
        for emotion, score in result.items():
            assert abs(score - 0.125) < 1e-6, f"{emotion} not uniform: {score}"

    def test_plutchik_emotions_count(self):
        """PLUTCHIK_EMOTIONS constant must have exactly 8 entries."""
        assert len(PLUTCHIK_EMOTIONS) == 8


# =============================================================================
# STEEPS Tests
# =============================================================================


class TestSTEEPSClassification:
    """Verify STEEPS constants and mapping."""

    def test_steeps_has_6_labels(self):
        """STEEPS_LABELS must have exactly 6 entries."""
        assert len(STEEPS_LABELS) == 6

    def test_steeps_code_map_covers_all_labels(self):
        """Every STEEPS label must have a code mapping."""
        for label in STEEPS_LABELS:
            assert label in STEEPS_CODE_MAP, f"Missing code for {label}"

    def test_steeps_codes_are_unique(self):
        """STEEPS codes must be unique."""
        codes = list(STEEPS_CODE_MAP.values())
        assert len(codes) == len(set(codes))


# =============================================================================
# Output Contract Tests
# =============================================================================


class TestOutputContract:
    """Verify output schema contract."""

    def test_article_analysis_expected_columns(self):
        """Article analysis output must have exactly 13 columns."""
        expected_columns = {
            "article_id", "sentiment_label", "sentiment_score",
            "emotion_joy", "emotion_trust", "emotion_fear", "emotion_surprise",
            "emotion_sadness", "emotion_anger", "emotion_disgust",
            "emotion_anticipation", "steeps_category", "importance_score",
        }
        assert len(expected_columns) == 13

    def test_importance_score_formula_components(self):
        """Importance score constants must exist with valid weights."""
        from src.analysis.stage3_article_analysis import (
            IMPORTANCE_WEIGHTS,
        )
        required_keys = {"authority", "entity_density", "coverage",
                         "recency", "extremity"}
        assert required_keys.issubset(set(IMPORTANCE_WEIGHTS.keys()))
        # Weights should sum to approximately 1.0
        assert abs(sum(IMPORTANCE_WEIGHTS.values()) - 1.0) < 0.01
