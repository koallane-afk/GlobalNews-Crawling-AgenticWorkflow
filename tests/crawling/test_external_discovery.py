"""Tests for Google News RSS and GDELT DOC API external URL discovery.

Covers:
    - GoogleNewsDiscovery: feed parsing, domain filtering, date handling,
      error resilience, deduplication.
    - GDELTDiscovery: JSON parsing, domain filtering, GDELT date format,
      curl_cffi/urllib fallback, error resilience.
    - URLDiscovery external fallback integration: threshold-based activation,
      deduplication against existing URLs, enable_external_fallback toggle.
    - Cache proxy extraction: Google AMP, Google Cache, archive.today
      fallback chain in article_extractor.

Reference:
    Task: Add Google News RSS and GDELT DOC API as URL discovery methods.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.crawling.contracts import DiscoveredURL
from src.crawling.url_discovery import (
    GoogleNewsDiscovery,
    GDELTDiscovery,
    URLDiscovery,
    normalize_url,
    GOOGLE_NEWS_RSS_BASE,
    GDELT_DOC_API_BASE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def google_news() -> GoogleNewsDiscovery:
    """Create a GoogleNewsDiscovery instance with short timeout."""
    return GoogleNewsDiscovery(timeout=5)


@pytest.fixture
def gdelt() -> GDELTDiscovery:
    """Create a GDELTDiscovery instance with short timeout."""
    return GDELTDiscovery(timeout=5, max_records=50, timespan="24h")


@pytest.fixture
def mock_network_guard() -> MagicMock:
    """Create a mock NetworkGuard that always raises (simulating blocked site)."""
    guard = MagicMock()
    from src.utils.error_handler import NetworkError
    guard.fetch.side_effect = NetworkError("blocked", status_code=403)
    return guard


# ---------------------------------------------------------------------------
# Helper: build RSS XML for Google News responses
# ---------------------------------------------------------------------------

def _build_google_news_rss(
    entries: list[dict[str, str]],
) -> str:
    """Build a minimal RSS 2.0 XML string for Google News RSS mock.

    Args:
        entries: List of dicts with keys: url, title, pub_date (RFC 2822).

    Returns:
        RSS XML string.
    """
    items = ""
    for entry in entries:
        items += f"""
        <item>
            <title>{entry.get('title', 'Test Article')}</title>
            <link>{entry.get('url', 'https://example.com/article1')}</link>
            <pubDate>{entry.get('pub_date', 'Mon, 17 Mar 2026 10:00:00 GMT')}</pubDate>
            <source url="{entry.get('source_url', entry.get('url', ''))}">Test Source</source>
        </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        {items}
    </channel>
</rss>"""


# ---------------------------------------------------------------------------
# GoogleNewsDiscovery Tests
# ---------------------------------------------------------------------------

class TestGoogleNewsDiscovery:
    """Test Google News RSS URL discovery."""

    def test_discover_parses_valid_rss(self, google_news: GoogleNewsDiscovery) -> None:
        """Valid Google News RSS feed is parsed into DiscoveredURL objects."""
        rss_xml = _build_google_news_rss([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Breaking News 1",
                "pub_date": "Mon, 17 Mar 2026 10:00:00 GMT",
            },
            {
                "url": "https://www.example.com/politics/story-2",
                "title": "Political Update",
                "pub_date": "Mon, 17 Mar 2026 09:00:00 GMT",
            },
        ])

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = []

        # Build feedparser-like entry objects
        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
                max_age_days=1,
            )

        assert len(results) == 2
        assert all(r.discovered_via == "google_news" for r in results)
        assert all(r.source_id == "example" for r in results)
        assert results[0].title_hint == "Breaking News 1"
        assert results[1].title_hint == "Political Update"

    def test_discover_filters_wrong_domain(self, google_news: GoogleNewsDiscovery) -> None:
        """URLs from other domains are filtered out."""
        rss_xml = _build_google_news_rss([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Our Article",
            },
            {
                "url": "https://www.otherdomain.com/news/article-2",
                "title": "Other Site Article",
            },
        ])

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1
        assert "example.com" in results[0].url

    def test_discover_respects_subdomain_matching(self, google_news: GoogleNewsDiscovery) -> None:
        """Subdomains of the target domain are accepted."""
        rss_xml = _build_google_news_rss([
            {
                "url": "https://news.example.com/article/breaking",
                "title": "Subdomain Article",
            },
        ])

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="example.com",
                source_id="example",
            )

        assert len(results) == 1

    def test_discover_filters_non_article_urls(self, google_news: GoogleNewsDiscovery) -> None:
        """Non-article URLs (category pages, etc.) are filtered out."""
        rss_xml = _build_google_news_rss([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Real Article",
            },
            {
                # This is just the homepage / section page
                "url": "https://www.example.com/",
                "title": "Home Page",
            },
        ])

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1
        assert "article-1" in results[0].url

    def test_discover_handles_feedparser_import_error(self) -> None:
        """Gracefully returns empty list when feedparser is not available."""
        gn = GoogleNewsDiscovery()

        with patch.dict("sys.modules", {"feedparser": None}):
            with patch("builtins.__import__", side_effect=ImportError("no feedparser")):
                # This will attempt to import feedparser and fail
                results = gn.discover("example.com", "example")

        assert results == []

    def test_discover_handles_network_timeout(self, google_news: GoogleNewsDiscovery) -> None:
        """Returns empty list on network timeout without raising."""
        import feedparser

        with patch("feedparser.parse", side_effect=Exception("timeout")):
            results = google_news.discover("example.com", "example")

        assert results == []

    def test_discover_handles_bozo_feed(self, google_news: GoogleNewsDiscovery) -> None:
        """Handles malformed feeds (bozo=True with no entries) gracefully."""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_feed.bozo_exception = Exception("malformed xml")

        with patch("feedparser.parse", return_value=mock_feed):
            results = google_news.discover("example.com", "example")

        assert results == []

    def test_discover_deduplicates_urls(self, google_news: GoogleNewsDiscovery) -> None:
        """Duplicate URLs from the same feed are deduplicated."""
        rss_xml = _build_google_news_rss([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Article 1 First",
            },
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Article 1 Duplicate",
            },
        ])

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1

    def test_discover_priority_is_3(self, google_news: GoogleNewsDiscovery) -> None:
        """Google News URLs have priority=3 (lower than direct discovery)."""
        rss_xml = _build_google_news_rss([
            {"url": "https://www.example.com/news/article-1"},
        ])

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert results[0].priority == 3

    def test_discover_respects_max_results(self, google_news: GoogleNewsDiscovery) -> None:
        """max_results parameter limits the number of returned URLs."""
        entries = [
            {
                "url": f"https://www.example.com/news/article-{i}",
                "title": f"Article {i}",
            }
            for i in range(20)
        ]
        rss_xml = _build_google_news_rss(entries)

        import feedparser
        parsed = feedparser.parse(rss_xml)

        with patch("feedparser.parse", return_value=parsed):
            results = google_news.discover(
                domain="www.example.com",
                source_id="example",
                max_results=5,
            )

        assert len(results) == 5


# ---------------------------------------------------------------------------
# GDELTDiscovery Tests
# ---------------------------------------------------------------------------

class TestGDELTDiscovery:
    """Test GDELT DOC API URL discovery."""

    def _make_gdelt_response(
        self, articles: list[dict[str, str]]
    ) -> str:
        """Build a GDELT artlist JSON response string."""
        return json.dumps({"articles": articles})

    def test_discover_parses_valid_json(self, gdelt: GDELTDiscovery) -> None:
        """Valid GDELT JSON response is parsed into DiscoveredURL objects."""
        response = self._make_gdelt_response([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Breaking News",
                "seendate": "20260317T100000Z",
            },
            {
                "url": "https://www.example.com/politics/story-2",
                "title": "Political Update",
                "seendate": "20260317T090000Z",
            },
        ])

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
                max_age_days=1,
            )

        assert len(results) == 2
        assert all(r.discovered_via == "gdelt" for r in results)
        assert all(r.source_id == "example" for r in results)
        assert results[0].title_hint == "Breaking News"

    def test_discover_filters_wrong_domain(self, gdelt: GDELTDiscovery) -> None:
        """URLs from other domains are filtered out."""
        response = self._make_gdelt_response([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Our Article",
                "seendate": "20260317T100000Z",
            },
            {
                "url": "https://www.otherdomain.com/news/article-2",
                "title": "Other Site",
                "seendate": "20260317T090000Z",
            },
        ])

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1

    def test_discover_handles_invalid_json(self, gdelt: GDELTDiscovery) -> None:
        """Malformed JSON returns empty list without raising."""
        with patch.object(gdelt, "_fetch_api", return_value="not json {{{"):
            results = gdelt.discover("example.com", "example")

        assert results == []

    def test_discover_handles_missing_articles_key(self, gdelt: GDELTDiscovery) -> None:
        """JSON without 'articles' key returns empty list."""
        with patch.object(gdelt, "_fetch_api", return_value='{"data": []}'):
            results = gdelt.discover("example.com", "example")

        assert results == []

    def test_discover_handles_fetch_failure(self, gdelt: GDELTDiscovery) -> None:
        """API fetch failure returns empty list."""
        with patch.object(gdelt, "_fetch_api", return_value=None):
            results = gdelt.discover("example.com", "example")

        assert results == []

    def test_discover_deduplicates_urls(self, gdelt: GDELTDiscovery) -> None:
        """Duplicate URLs are deduplicated."""
        response = self._make_gdelt_response([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "First",
                "seendate": "20260317T100000Z",
            },
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Duplicate",
                "seendate": "20260317T090000Z",
            },
        ])

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1

    def test_discover_priority_is_4(self, gdelt: GDELTDiscovery) -> None:
        """GDELT URLs have priority=4 (lower than google_news)."""
        response = self._make_gdelt_response([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Test",
                "seendate": "20260317T100000Z",
            },
        ])

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert results[0].priority == 4

    def test_parse_gdelt_date_compact_format(self) -> None:
        """GDELT compact date format (YYYYMMDDTHHMMSSZ) is parsed correctly."""
        dt = GDELTDiscovery._parse_gdelt_date("20260317T143000Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 17
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_parse_gdelt_date_empty(self) -> None:
        """Empty date string returns None."""
        assert GDELTDiscovery._parse_gdelt_date("") is None
        assert GDELTDiscovery._parse_gdelt_date(None) is None  # type: ignore[arg-type]

    def test_parse_gdelt_date_fallback_to_general(self) -> None:
        """Non-GDELT date format falls back to the general parser."""
        dt = GDELTDiscovery._parse_gdelt_date("2026-03-17T14:30:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_fetch_api_tries_curl_then_urllib(self, gdelt: GDELTDiscovery) -> None:
        """_fetch_api tries curl_cffi first, falls back to urllib."""
        # Mock curl_cffi to raise ImportError
        with patch.dict("sys.modules", {"curl_cffi": None, "curl_cffi.requests": None}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_resp.read.return_value = b'{"articles": []}'
                mock_resp.__enter__ = lambda s: s
                mock_resp.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_resp

                result = gdelt._fetch_api("https://api.gdelt.org/test", "test")

        assert result == '{"articles": []}'

    def test_discover_respects_max_results(self, gdelt: GDELTDiscovery) -> None:
        """max_results parameter limits returned URLs."""
        articles = [
            {
                "url": f"https://www.example.com/news/article-{i}",
                "title": f"Article {i}",
                "seendate": "20260317T100000Z",
            }
            for i in range(20)
        ]
        response = self._make_gdelt_response(articles)

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
                max_results=5,
            )

        assert len(results) == 5

    def test_discover_html_entity_decoding(self, gdelt: GDELTDiscovery) -> None:
        """HTML entities in titles are unescaped."""
        response = self._make_gdelt_response([
            {
                "url": "https://www.example.com/news/article-1",
                "title": "Markets &amp; Economy: A &quot;Complex&quot; Outlook",
                "seendate": "20260317T100000Z",
            },
        ])

        with patch.object(gdelt, "_fetch_api", return_value=response):
            results = gdelt.discover(
                domain="www.example.com",
                source_id="example",
            )

        assert len(results) == 1
        assert "&amp;" not in results[0].title_hint
        assert "&quot;" not in results[0].title_hint
        assert '"Complex"' in results[0].title_hint

    def test_discover_max_records_capped_at_250(self) -> None:
        """max_records constructor parameter is capped at 250 (GDELT API limit)."""
        gdelt = GDELTDiscovery(max_records=500)
        assert gdelt._max_records == 250

    def test_discover_adjusts_timespan_for_long_lookback(self, gdelt: GDELTDiscovery) -> None:
        """max_age_days > 2 adjusts the timespan parameter."""
        with patch.object(gdelt, "_fetch_api", return_value=None) as mock_fetch:
            gdelt.discover("example.com", "example", max_age_days=7)

        # The API URL should include timespan=168h (7*24)
        call_args = mock_fetch.call_args[0][0]
        assert "timespan=168h" in call_args


# ---------------------------------------------------------------------------
# URLDiscovery External Fallback Integration Tests
# ---------------------------------------------------------------------------

class TestURLDiscoveryExternalFallback:
    """Test integration of external fallback into URLDiscovery.discover()."""

    def test_external_fallback_activates_below_threshold(
        self, mock_network_guard: MagicMock
    ) -> None:
        """External fallback is triggered when primary methods find < threshold URLs."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=5,
            enable_external_fallback=True,
        )

        site_config = {
            "url": "https://www.blocked-site.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.blocked-site.com/rss",
                "fallback_methods": [],
            },
        }

        # Mock the RSS parser to return 0 URLs (site is blocked)
        with patch.object(discovery._rss_parser, "parse_feed", return_value=[]):
            # Mock Google News to return some URLs
            mock_gn_urls = [
                DiscoveredURL(
                    url=f"https://www.blocked-site.com/news/article-{i}",
                    source_id="blocked",
                    discovered_via="google_news",
                    priority=3,
                )
                for i in range(3)
            ]
            with patch.object(discovery._google_news, "discover", return_value=mock_gn_urls):
                # Mock GDELT to return some URLs
                mock_gdelt_urls = [
                    DiscoveredURL(
                        url=f"https://www.blocked-site.com/world/story-{i}",
                        source_id="blocked",
                        discovered_via="gdelt",
                        priority=4,
                    )
                    for i in range(3)
                ]
                with patch.object(discovery._gdelt, "discover", return_value=mock_gdelt_urls):
                    results = discovery.discover(site_config, "blocked")

        # Should have URLs from both external sources
        assert len(results) == 6
        gn_count = sum(1 for r in results if r.discovered_via == "google_news")
        gdelt_count = sum(1 for r in results if r.discovered_via == "gdelt")
        assert gn_count == 3
        assert gdelt_count == 3

    def test_external_fallback_skipped_when_threshold_met(
        self, mock_network_guard: MagicMock
    ) -> None:
        """External fallback is NOT triggered when primary methods find >= threshold URLs."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=3,
            enable_external_fallback=True,
        )

        site_config = {
            "url": "https://www.example.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.example.com/rss",
                "fallback_methods": [],
            },
        }

        # Mock RSS to return enough URLs
        rss_urls = [
            DiscoveredURL(
                url=f"https://www.example.com/news/article-{i}",
                source_id="example",
                discovered_via="rss",
            )
            for i in range(5)
        ]
        with patch.object(discovery._rss_parser, "parse_feed", return_value=rss_urls):
            with patch.object(
                discovery._google_news, "discover"
            ) as mock_gn:
                results = discovery.discover(site_config, "example")

        # External fallback should not have been called
        mock_gn.assert_not_called()
        assert len(results) == 5

    def test_external_fallback_disabled(
        self, mock_network_guard: MagicMock
    ) -> None:
        """External fallback is NOT triggered when enable_external_fallback=False."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=5,
            enable_external_fallback=False,
        )

        site_config = {
            "url": "https://www.blocked-site.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.blocked-site.com/rss",
                "fallback_methods": [],
            },
        }

        with patch.object(discovery._rss_parser, "parse_feed", return_value=[]):
            with patch.object(
                discovery._google_news, "discover"
            ) as mock_gn:
                results = discovery.discover(site_config, "blocked")

        mock_gn.assert_not_called()
        assert len(results) == 0

    def test_external_fallback_deduplicates_against_existing(
        self, mock_network_guard: MagicMock
    ) -> None:
        """External URLs that duplicate existing URLs are filtered out."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=10,
            enable_external_fallback=True,
        )

        site_config = {
            "url": "https://www.example.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.example.com/rss",
                "fallback_methods": [],
            },
        }

        # RSS finds 2 URLs
        rss_urls = [
            DiscoveredURL(
                url="https://www.example.com/news/article-1",
                source_id="example",
                discovered_via="rss",
            ),
            DiscoveredURL(
                url="https://www.example.com/news/article-2",
                source_id="example",
                discovered_via="rss",
            ),
        ]

        # Google News returns one duplicate and one new
        gn_urls = [
            DiscoveredURL(
                url="https://www.example.com/news/article-1",  # duplicate
                source_id="example",
                discovered_via="google_news",
            ),
            DiscoveredURL(
                url="https://www.example.com/news/article-3",  # new
                source_id="example",
                discovered_via="google_news",
            ),
        ]

        with patch.object(discovery._rss_parser, "parse_feed", return_value=rss_urls):
            with patch.object(discovery._google_news, "discover", return_value=gn_urls):
                with patch.object(discovery._gdelt, "discover", return_value=[]):
                    results = discovery.discover(site_config, "example")

        # 2 from RSS + 1 new from Google News (duplicate filtered)
        assert len(results) == 3
        urls = {r.url for r in results}
        assert "https://www.example.com/news/article-1" in urls
        assert "https://www.example.com/news/article-2" in urls
        assert "https://www.example.com/news/article-3" in urls

    def test_extract_domain(self) -> None:
        """_extract_domain extracts domain from various URL formats."""
        assert URLDiscovery._extract_domain("https://www.bbc.com") == "www.bbc.com"
        assert URLDiscovery._extract_domain("https://example.com/path") == "example.com"
        assert URLDiscovery._extract_domain("http://news.site.co.kr/") == "news.site.co.kr"
        assert URLDiscovery._extract_domain("") == ""
        assert URLDiscovery._extract_domain("not-a-url") == ""

    def test_gdelt_skipped_if_google_news_sufficient(
        self, mock_network_guard: MagicMock
    ) -> None:
        """GDELT is skipped if Google News already provides enough URLs."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=3,
            enable_external_fallback=True,
        )

        site_config = {
            "url": "https://www.blocked-site.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.blocked-site.com/rss",
                "fallback_methods": [],
            },
        }

        # RSS returns nothing
        # Google News returns 5 URLs (above threshold of 3)
        gn_urls = [
            DiscoveredURL(
                url=f"https://www.blocked-site.com/news/article-{i}",
                source_id="blocked",
                discovered_via="google_news",
                priority=3,
            )
            for i in range(5)
        ]

        with patch.object(discovery._rss_parser, "parse_feed", return_value=[]):
            with patch.object(discovery._google_news, "discover", return_value=gn_urls):
                with patch.object(discovery._gdelt, "discover") as mock_gdelt:
                    results = discovery.discover(site_config, "blocked")

        # GDELT should not have been called since Google News provided enough
        mock_gdelt.assert_not_called()
        assert len(results) == 5

    def test_external_fallback_error_resilience(
        self, mock_network_guard: MagicMock
    ) -> None:
        """External fallback handles errors gracefully without crashing."""
        discovery = URLDiscovery(
            mock_network_guard,
            min_urls_threshold=5,
            enable_external_fallback=True,
        )

        site_config = {
            "url": "https://www.blocked-site.com",
            "crawl": {
                "primary_method": "rss",
                "rss_url": "https://www.blocked-site.com/rss",
                "fallback_methods": [],
            },
        }

        with patch.object(discovery._rss_parser, "parse_feed", return_value=[]):
            # Both external services raise exceptions
            with patch.object(
                discovery._google_news, "discover",
                side_effect=Exception("network error"),
            ):
                with patch.object(
                    discovery._gdelt, "discover",
                    side_effect=Exception("timeout"),
                ):
                    # Should not raise -- returns empty list
                    results = discovery.discover(site_config, "blocked")

        assert results == []


# ---------------------------------------------------------------------------
# Cache Proxy Extraction Tests
# ---------------------------------------------------------------------------

class TestCacheProxyExtraction:
    """Test cache/proxy extraction fallback in article_extractor."""

    def test_fetch_via_cache_proxies_tries_services_in_order(self) -> None:
        """fetch_via_cache_proxies tries AMP -> Google Cache -> archive.today."""
        from src.crawling.article_extractor import fetch_via_cache_proxies

        call_order = []

        def mock_amp(url: str) -> str | None:
            call_order.append("amp")
            return None

        def mock_cache(url: str) -> str | None:
            call_order.append("cache")
            return "<html>cached</html>"

        def mock_archive(url: str) -> str | None:
            call_order.append("archive")
            return None

        with patch(
            "src.crawling.article_extractor._fetch_via_google_amp", mock_amp
        ):
            with patch(
                "src.crawling.article_extractor._fetch_via_google_cache", mock_cache
            ):
                with patch(
                    "src.crawling.article_extractor._fetch_via_archive_today",
                    mock_archive,
                ):
                    html, service = fetch_via_cache_proxies(
                        "https://example.com/article"
                    )

        assert html == "<html>cached</html>"
        assert service == "google_cache"
        # AMP was tried first, then cache succeeded -- archive not tried
        assert call_order == ["amp", "cache"]

    def test_fetch_via_cache_proxies_returns_none_when_all_fail(self) -> None:
        """Returns (None, '') when all cache services fail."""
        from src.crawling.article_extractor import fetch_via_cache_proxies

        with patch(
            "src.crawling.article_extractor._fetch_via_google_amp", return_value=None
        ):
            with patch(
                "src.crawling.article_extractor._fetch_via_google_cache",
                return_value=None,
            ):
                with patch(
                    "src.crawling.article_extractor._fetch_via_archive_today",
                    return_value=None,
                ):
                    html, service = fetch_via_cache_proxies(
                        "https://example.com/article"
                    )

        assert html is None
        assert service == ""

    def test_fetch_via_cache_proxies_handles_exceptions(self) -> None:
        """Cache proxy functions that raise are caught gracefully."""
        from src.crawling.article_extractor import fetch_via_cache_proxies

        with patch(
            "src.crawling.article_extractor._fetch_via_google_amp",
            side_effect=Exception("boom"),
        ):
            with patch(
                "src.crawling.article_extractor._fetch_via_google_cache",
                side_effect=Exception("bang"),
            ):
                with patch(
                    "src.crawling.article_extractor._fetch_via_archive_today",
                    return_value="<html>archived</html>",
                ):
                    html, service = fetch_via_cache_proxies(
                        "https://example.com/article"
                    )

        assert html == "<html>archived</html>"
        assert service == "archive_today"

    def test_external_discovery_methods_constant(self) -> None:
        """EXTERNAL_DISCOVERY_METHODS contains expected values."""
        from src.crawling.article_extractor import EXTERNAL_DISCOVERY_METHODS

        assert "google_news" in EXTERNAL_DISCOVERY_METHODS
        assert "gdelt" in EXTERNAL_DISCOVERY_METHODS
        assert "rss" not in EXTERNAL_DISCOVERY_METHODS

    def test_google_amp_url_construction(self) -> None:
        """Google AMP URL is correctly constructed from article URL."""
        from src.crawling.article_extractor import _fetch_via_google_amp

        with patch(
            "src.crawling.article_extractor._fetch_cache_url"
        ) as mock_fetch:
            mock_fetch.return_value = None
            _fetch_via_google_amp("https://www.example.com/news/article-1")

        expected_url = "https://cdn.ampproject.org/c/s/www.example.com/news/article-1"
        mock_fetch.assert_called_once_with(expected_url, "google_amp", 20)

    def test_google_cache_url_construction(self) -> None:
        """Google Cache URL is correctly constructed."""
        from src.crawling.article_extractor import _fetch_via_google_cache

        with patch(
            "src.crawling.article_extractor._fetch_cache_url"
        ) as mock_fetch:
            mock_fetch.return_value = None
            _fetch_via_google_cache("https://www.example.com/news/article-1")

        call_url = mock_fetch.call_args[0][0]
        assert "webcache.googleusercontent.com" in call_url
        assert "cache:" in call_url

    def test_archive_today_url_construction(self) -> None:
        """archive.today URL is correctly constructed."""
        from src.crawling.article_extractor import _fetch_via_archive_today

        with patch(
            "src.crawling.article_extractor._fetch_cache_url"
        ) as mock_fetch:
            mock_fetch.return_value = None
            _fetch_via_archive_today("https://www.example.com/news/article-1")

        expected_url = "https://archive.today/newest/https://www.example.com/news/article-1"
        mock_fetch.assert_called_once_with(expected_url, "archive_today", 20)


# ---------------------------------------------------------------------------
# ArticleExtractor Cache Proxy Integration Tests
# ---------------------------------------------------------------------------

class TestArticleExtractorCacheProxy:
    """Test that ArticleExtractor uses cache proxies for blocked external URLs."""

    def test_extract_uses_cache_proxy_on_403_for_external_url(self) -> None:
        """When direct fetch returns 403 and URL is from external discovery,
        cache proxy fallback is attempted."""
        from src.crawling.article_extractor import ArticleExtractor
        from src.crawling.network_guard import NetworkGuard
        from src.utils.error_handler import NetworkError

        guard = MagicMock(spec=NetworkGuard)
        guard.fetch.side_effect = NetworkError("forbidden", status_code=403, url="https://blocked.com/article")

        extractor = ArticleExtractor(guard, use_fundus=False)

        cached_html = """
        <html>
        <head><title>Cached Article Title</title>
        <meta property="og:title" content="Cached Article Title">
        </head>
        <body><article>
        <p>This is the cached article body text that is long enough to pass
        the minimum body length check which requires at least 100 characters
        of content to consider the extraction successful.</p>
        </article></body>
        </html>
        """

        site_config = {
            "name": "Blocked Site",
            "language": "en",
            "extraction": {},
        }

        with patch(
            "src.crawling.article_extractor.fetch_via_cache_proxies",
            return_value=(cached_html, "google_cache"),
        ):
            result = extractor.extract(
                url="https://blocked.com/news/article-1",
                source_id="blocked",
                site_config=site_config,
                discovered_via="google_news",
            )

        assert result.title is not None
        assert len(result.title) > 0
        # crawl_method should reflect the external discovery + cache proxy
        assert "google_cache" in result.crawl_method

    def test_extract_raises_when_cache_proxy_fails_for_external_url(self) -> None:
        """When cache proxy also fails for an external URL, NetworkError is raised."""
        from src.crawling.article_extractor import ArticleExtractor
        from src.crawling.network_guard import NetworkGuard
        from src.utils.error_handler import NetworkError

        guard = MagicMock(spec=NetworkGuard)
        guard.fetch.side_effect = NetworkError("forbidden", status_code=403, url="https://blocked.com/article")

        extractor = ArticleExtractor(guard, use_fundus=False)

        site_config = {
            "name": "Blocked Site",
            "language": "en",
            "extraction": {},
        }

        with patch(
            "src.crawling.article_extractor.fetch_via_cache_proxies",
            return_value=(None, ""),
        ):
            with pytest.raises(NetworkError, match="cache proxies failed"):
                extractor.extract(
                    url="https://blocked.com/news/article-1",
                    source_id="blocked",
                    site_config=site_config,
                    discovered_via="gdelt",
                )

    def test_extract_normal_fetch_does_not_use_cache_proxy(self) -> None:
        """For non-external URLs, 403 does NOT trigger cache proxy fallback."""
        from src.crawling.article_extractor import ArticleExtractor
        from src.crawling.network_guard import NetworkGuard
        from src.utils.error_handler import NetworkError

        guard = MagicMock(spec=NetworkGuard)
        guard.fetch.side_effect = NetworkError("forbidden", status_code=403, url="https://normal.com/article")

        extractor = ArticleExtractor(guard, use_fundus=False)

        site_config = {
            "name": "Normal Site",
            "language": "en",
            "extraction": {},
        }

        with patch(
            "src.crawling.article_extractor.fetch_via_cache_proxies"
        ) as mock_cache:
            with pytest.raises(NetworkError):
                extractor.extract(
                    url="https://normal.com/news/article-1",
                    source_id="normal",
                    site_config=site_config,
                    # No discovered_via -- normal RSS discovery
                )

        # Cache proxy should NOT have been called
        mock_cache.assert_not_called()

    def test_extract_with_block_error_triggers_cache_proxy_for_external(self) -> None:
        """BlockDetectedError triggers cache proxy for external discovery URLs."""
        from src.crawling.article_extractor import ArticleExtractor
        from src.crawling.network_guard import NetworkGuard
        from src.utils.error_handler import BlockDetectedError

        guard = MagicMock(spec=NetworkGuard)
        guard.fetch.side_effect = BlockDetectedError(
            "captcha detected", block_type="captcha"
        )

        extractor = ArticleExtractor(guard, use_fundus=False)

        cached_html = """
        <html>
        <head><meta property="og:title" content="Recovered Article"></head>
        <body><article>
        <p>This is article content recovered from the cache proxy that is
        long enough to pass the minimum body length threshold for extraction.</p>
        </article></body>
        </html>
        """

        site_config = {
            "name": "Blocked Site",
            "language": "en",
            "extraction": {},
        }

        with patch(
            "src.crawling.article_extractor.fetch_via_cache_proxies",
            return_value=(cached_html, "google_amp"),
        ):
            result = extractor.extract(
                url="https://blocked.com/news/article-1",
                source_id="blocked",
                site_config=site_config,
                discovered_via="google_news",  # External discovery triggers cache proxy
            )

        assert result.title is not None
        assert "google_amp" in result.crawl_method

    def test_extract_block_error_does_not_trigger_cache_proxy_for_rss(self) -> None:
        """BlockDetectedError does NOT trigger cache proxy for RSS-discovered URLs.

        RSS-discovered URLs should let the anti-block escalation system handle
        the block, not the cache proxy fallback.
        """
        from src.crawling.article_extractor import ArticleExtractor
        from src.crawling.network_guard import NetworkGuard
        from src.utils.error_handler import BlockDetectedError

        guard = MagicMock(spec=NetworkGuard)
        guard.fetch.side_effect = BlockDetectedError(
            "captcha detected", block_type="captcha"
        )

        extractor = ArticleExtractor(guard, use_fundus=False)

        site_config = {
            "name": "Blocked Site",
            "language": "en",
            "extraction": {},
        }

        with patch(
            "src.crawling.article_extractor.fetch_via_cache_proxies"
        ) as mock_cache:
            with pytest.raises(BlockDetectedError):
                extractor.extract(
                    url="https://blocked.com/news/article-1",
                    source_id="blocked",
                    site_config=site_config,
                    discovered_via="rss",
                )

        # Cache proxy should NOT have been called for RSS discovery
        mock_cache.assert_not_called()
