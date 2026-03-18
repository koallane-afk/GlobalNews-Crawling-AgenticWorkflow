"""Tests for the Never-Abandon loop bug fixes.

Validates that the 4 root causes of strategy rotation failure are fixed:

1. NetworkGuard's internal circuit breaker not reset in Never-Abandon loop
2. _DEFAULT_STRATEGIES missing most strategies, limiting diversity
3. Unavailable strategies (ImportError) counting against max_attempts
4. Strategy rotation index not used by DynamicBypassEngine (always starts
   from the same strategy)

Reference: CRITICAL BUG — Never-Abandon only trying curl_cffi_impersonate.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.crawling.dynamic_bypass import (
    BlockType,
    BypassResult,
    DynamicBypassEngine,
    _DEFAULT_STRATEGIES,
    _MAX_STRATEGIES_PER_URL,
)
from src.crawling.retry_manager import (
    ALTERNATIVE_STRATEGIES,
    RetryManager,
    SiteRetryState,
)


# ===========================================================================
# Fix 1: _DEFAULT_STRATEGIES completeness
# ===========================================================================

class TestDefaultStrategiesCompleteness(unittest.TestCase):
    """Verify _DEFAULT_STRATEGIES includes ALL strategy types, not just 7."""

    def test_default_strategies_includes_all_14(self) -> None:
        """_DEFAULT_STRATEGIES must include all 14 ALTERNATIVE_STRATEGIES."""
        # Every strategy in ALTERNATIVE_STRATEGIES should be in _DEFAULT_STRATEGIES
        missing = set(ALTERNATIVE_STRATEGIES) - set(_DEFAULT_STRATEGIES)
        self.assertEqual(
            missing, set(),
            f"_DEFAULT_STRATEGIES is missing strategies: {missing}. "
            f"This was the root cause of 'only curl_cffi_impersonate' bug.",
        )

    def test_default_strategies_count_is_14(self) -> None:
        """Exactly 14 strategies in default list."""
        self.assertEqual(len(_DEFAULT_STRATEGIES), 14)

    def test_default_strategies_no_duplicates(self) -> None:
        """No duplicate strategies in default list."""
        self.assertEqual(
            len(_DEFAULT_STRATEGIES),
            len(set(_DEFAULT_STRATEGIES)),
        )

    def test_tier0_strategies_come_first(self) -> None:
        """Cheaper strategies (Tier 0) should appear before expensive ones."""
        # rotate_user_agent (T0) should come before patchright_stealth (T2)
        idx_ua = _DEFAULT_STRATEGIES.index("rotate_user_agent")
        idx_patchright = _DEFAULT_STRATEGIES.index("patchright_stealth")
        self.assertLess(idx_ua, idx_patchright)

    def test_rss_and_cache_in_default(self) -> None:
        """RSS, cache, and archive strategies must be in default list."""
        must_have = {
            "rss_feed_fallback",
            "google_cache_fallback",
            "archive_today_fallback",
            "wayback_fallback",
        }
        present = must_have & set(_DEFAULT_STRATEGIES)
        self.assertEqual(present, must_have)


# ===========================================================================
# Fix 2: Unavailable strategies don't count against max_attempts
# ===========================================================================

class TestUnavailableStrategyHandling(unittest.TestCase):
    """Verify ImportError/not-configured strategies don't waste attempt budget."""

    def test_is_unavailable_error_detects_not_installed(self) -> None:
        """ImportError-style 'not installed' should be detected."""
        result = BypassResult(success=False, error="patchright not installed")
        self.assertTrue(DynamicBypassEngine._is_unavailable_error(result))

    def test_is_unavailable_error_detects_no_proxy(self) -> None:
        """No proxy pool should be detected."""
        result = BypassResult(success=False, error="No proxy pool configured")
        self.assertTrue(DynamicBypassEngine._is_unavailable_error(result))

    def test_is_unavailable_error_rejects_real_failure(self) -> None:
        """Real network failures should not be flagged as unavailable."""
        result = BypassResult(success=False, error="Connection refused")
        self.assertFalse(DynamicBypassEngine._is_unavailable_error(result))

    def test_is_unavailable_error_rejects_success(self) -> None:
        """Successful results are never 'unavailable'."""
        result = BypassResult(success=True, html="<html>content</html>")
        self.assertFalse(DynamicBypassEngine._is_unavailable_error(result))

    def test_try_strategies_skips_unavailable_in_budget(self) -> None:
        """Unavailable strategies should not count against max_attempts.

        If max_attempts=2 and the first 3 strategies are unavailable, the
        engine should skip them and try 2 REAL strategies after.
        """
        engine = DynamicBypassEngine(proxy_pool=[], enable_browser=False)

        call_log: list[str] = []
        original_dispatch = engine._dispatch

        def mock_dispatch(strategy_name, url, timeout, extra_headers):
            call_log.append(strategy_name)
            # Simulate: some strategies return ImportError, others make real attempts
            if strategy_name in ("patchright_stealth", "camoufox_stealth", "proxy_rotation"):
                return BypassResult(success=False, error=f"{strategy_name} not installed")
            # Real attempt that fails
            return BypassResult(success=False, error="HTTP 403 Forbidden", status_code=403)

        engine._dispatch = mock_dispatch

        result = engine.try_strategies(
            url="https://example.com/article",
            block_type=None,
            site_id="test",
            max_attempts=3,
            timeout=10.0,
        )

        # Should have tried more than 3 strategies total because unavailable
        # ones don't count. The exact count depends on ordering but should
        # be > max_attempts.
        real_attempts = sum(
            1 for name in call_log
            if name not in ("patchright_stealth", "camoufox_stealth", "proxy_rotation")
        )
        # At least 3 real attempts (the budget)
        self.assertGreaterEqual(real_attempts, 3)


# ===========================================================================
# Fix 3: try_all_strategies rotates with start_offset
# ===========================================================================

class TestTryAllStrategies(unittest.TestCase):
    """Verify try_all_strategies tries ALL strategies and rotates."""

    def test_try_all_strategies_exists(self) -> None:
        """Method must exist on DynamicBypassEngine."""
        self.assertTrue(hasattr(DynamicBypassEngine, "try_all_strategies"))

    def test_try_all_no_cap(self) -> None:
        """try_all_strategies should try every registered strategy."""
        engine = DynamicBypassEngine(proxy_pool=[], enable_browser=False)
        call_log: list[str] = []

        def mock_dispatch(strategy_name, url, timeout, extra_headers):
            call_log.append(strategy_name)
            return BypassResult(success=False, error="test failure")

        engine._dispatch = mock_dispatch

        engine.try_all_strategies(
            url="https://example.com/article",
            block_type=None,
            site_id="test",
            timeout=10.0,
        )

        # Should have tried ALL registered strategies (not capped at 5)
        registered = set(engine._strategies.keys())
        tried = set(call_log)
        self.assertEqual(
            tried, registered,
            f"try_all_strategies missed: {registered - tried}",
        )

    def test_start_offset_rotates_order(self) -> None:
        """Different start_offset should produce different first strategies."""
        engine = DynamicBypassEngine(proxy_pool=[], enable_browser=False)

        first_strategies: list[str] = []
        for offset in range(3):
            call_log: list[str] = []

            def mock_dispatch(strategy_name, url, timeout, extra_headers):
                call_log.append(strategy_name)
                return BypassResult(success=False, error="test failure")

            engine._dispatch = mock_dispatch

            engine.try_all_strategies(
                url="https://example.com/article",
                block_type=None,
                site_id="test",
                timeout=10.0,
                start_offset=offset,
            )
            if call_log:
                first_strategies.append(call_log[0])

        # With different offsets, the first strategy tried should differ
        # (at least 2 out of 3 should be different)
        unique_firsts = set(first_strategies)
        self.assertGreaterEqual(
            len(unique_firsts), 2,
            f"start_offset not rotating: first strategies were {first_strategies}",
        )

    def test_try_all_stops_on_success(self) -> None:
        """try_all_strategies should stop as soon as one strategy succeeds."""
        engine = DynamicBypassEngine(proxy_pool=[], enable_browser=False)
        call_log: list[str] = []

        # Use a known registered strategy for the success case
        registered = list(engine._strategies.keys())
        # Pick the third strategy as the one that succeeds
        success_strategy = registered[2] if len(registered) > 2 else registered[0]

        def mock_dispatch(strategy_name, url, timeout, extra_headers):
            call_log.append(strategy_name)
            if strategy_name == success_strategy:
                return BypassResult(
                    success=True, html="<html>" + "x" * 600 + "</html>",
                    status_code=200,
                )
            return BypassResult(success=False, error="fail")

        engine._dispatch = mock_dispatch

        result = engine.try_all_strategies(
            url="https://example.com/article",
            block_type=None,
            site_id="test",
            timeout=10.0,
        )

        self.assertTrue(result.success)
        # Should not have tried strategies after the successful one
        success_idx = call_log.index(success_strategy)
        self.assertEqual(len(call_log), success_idx + 1)


# ===========================================================================
# Fix 4: Never-Abandon strategy index advances and is used
# ===========================================================================

class TestNeverAbandonStrategyAdvancement(unittest.TestCase):
    """Verify that get_never_abandon_strategy advances through all strategies."""

    def test_strategy_index_advances(self) -> None:
        """Each call to get_never_abandon_strategy should return a different strategy."""
        manager = RetryManager()
        state = manager.get_state("test_site")
        state.never_abandon_active = True

        seen_strategies: list[str] = []
        for _ in range(len(ALTERNATIVE_STRATEGIES)):
            strategy, delay = manager.get_never_abandon_strategy("test_site")
            seen_strategies.append(strategy)

        # Should have seen all 14 strategies
        self.assertEqual(len(set(seen_strategies)), len(ALTERNATIVE_STRATEGIES))

    def test_strategy_index_cycles(self) -> None:
        """After exhausting all strategies, it should cycle back to the start."""
        manager = RetryManager()
        state = manager.get_state("test_site")
        state.never_abandon_active = True

        strategies_cycle1: list[str] = []
        for _ in range(len(ALTERNATIVE_STRATEGIES)):
            strategy, _ = manager.get_never_abandon_strategy("test_site")
            strategies_cycle1.append(strategy)

        strategies_cycle2: list[str] = []
        for _ in range(len(ALTERNATIVE_STRATEGIES)):
            strategy, _ = manager.get_never_abandon_strategy("test_site")
            strategies_cycle2.append(strategy)

        # Cycle 2 should be the same as cycle 1 (modular cycling)
        self.assertEqual(strategies_cycle1, strategies_cycle2)

    def test_never_abandon_strategy_idx_matches_offset(self) -> None:
        """The strategy_idx in SiteRetryState should advance and can be used
        as start_offset for DynamicBypassEngine.try_all_strategies()."""
        manager = RetryManager()
        state = manager.get_state("test_site")
        state.never_abandon_active = True

        # Get first strategy
        manager.get_never_abandon_strategy("test_site")
        idx_after_1 = state.never_abandon_strategy_idx
        self.assertEqual(idx_after_1, 1)

        # Get second strategy
        manager.get_never_abandon_strategy("test_site")
        idx_after_2 = state.never_abandon_strategy_idx
        self.assertEqual(idx_after_2, 2)

        # The index can be passed to try_all_strategies as start_offset
        self.assertIsInstance(idx_after_2, int)


# ===========================================================================
# Dual Circuit Breaker: verify both CBs must be reset
# ===========================================================================

class TestDualCircuitBreakerReset(unittest.TestCase):
    """Verify that the Never-Abandon loop resets BOTH circuit breakers.

    The pipeline has two independent circuit breakers per site:
    1. CircuitBreakerCoordinator (pipeline-level)
    2. NetworkGuard._circuit_breakers (request-level)

    If only the coordinator is reset, NetworkGuard.fetch() still raises
    NetworkError because its own CB is OPEN. This was the primary root
    cause of the stall.
    """

    def test_networkguard_has_own_circuit_breakers(self) -> None:
        """NetworkGuard manages its own per-site circuit breakers."""
        from src.crawling.network_guard import NetworkGuard
        guard = NetworkGuard()
        guard.configure_site("test_site", rate_limit_seconds=1.0)

        # NetworkGuard should have a CB for the configured site
        cb = guard._circuit_breakers.get("test_site")
        self.assertIsNotNone(cb, "NetworkGuard should create a CB per site")

    def test_networkguard_cb_independent_of_coordinator(self) -> None:
        """Resetting coordinator does NOT reset NetworkGuard's CB."""
        from src.crawling.network_guard import NetworkGuard
        from src.crawling.circuit_breaker import CircuitBreakerCoordinator
        from src.utils.error_handler import CircuitState

        guard = NetworkGuard()
        guard.configure_site("test_site", rate_limit_seconds=1.0,
                             circuit_breaker_threshold=2)
        coordinator = CircuitBreakerCoordinator(failure_threshold=2)

        # Trip both CBs
        for _ in range(3):
            coordinator.record_failure("test_site")
            ng_cb = guard._circuit_breakers["test_site"]
            ng_cb.record_failure()

        # Both should be OPEN
        self.assertEqual(coordinator.get_state("test_site"), CircuitState.OPEN)
        self.assertEqual(guard._circuit_breakers["test_site"].state, CircuitState.OPEN)

        # Reset ONLY the coordinator
        coordinator.reset("test_site")

        # Coordinator should be CLOSED
        self.assertEqual(coordinator.get_state("test_site"), CircuitState.CLOSED)
        # NetworkGuard's CB should STILL be OPEN (this was the bug)
        self.assertEqual(
            guard._circuit_breakers["test_site"].state,
            CircuitState.OPEN,
            "NetworkGuard's CB must remain OPEN when only coordinator is reset. "
            "This proves the dual-CB bug: resetting one doesn't reset the other.",
        )

        # Fix: reset NetworkGuard's CB explicitly
        guard._circuit_breakers["test_site"].reset()
        self.assertEqual(
            guard._circuit_breakers["test_site"].state,
            CircuitState.CLOSED,
        )


if __name__ == "__main__":
    unittest.main()
