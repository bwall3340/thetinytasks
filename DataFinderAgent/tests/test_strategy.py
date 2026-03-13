"""Tests for the strategy engine."""

import pytest
from agent.strategy import StrategyEngine, DifficultyAssessment
from agent.tools.base import ScrapeMetadata
from agent.state import AgentState, ScrapeAttempt


class TestDifficultyScoring:
    def setup_method(self):
        self.engine = StrategyEngine()

    def _meta(self, **kwargs) -> ScrapeMetadata:
        return ScrapeMetadata(url="https://example.com", **kwargs)

    def test_clean_page_scores_1(self):
        meta = self._meta(status_code=200, has_captcha=False, has_cloudflare=False, is_js_required=False)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.score == 1
        assert assessment.recommended_tool == "general_scrape"

    def test_js_required_escalates_to_dynamic(self):
        meta = self._meta(status_code=200, is_js_required=True)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.score >= 2
        assert assessment.recommended_tool == "dynamic_scrape"

    def test_cloudflare_scores_high(self):
        meta = self._meta(status_code=403, has_cloudflare=True)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.score >= 4

    def test_captcha_scores_max(self):
        meta = self._meta(status_code=200, has_captcha=True)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.score == 5
        assert "captcha" in assessment.notes.lower()

    def test_captcha_recommends_alternative(self):
        meta = self._meta(status_code=200, has_captcha=True)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.recommended_tool == "alternative_source"

    def test_rate_limited_scores_3(self):
        meta = self._meta(status_code=429)
        assessment = self.engine.assess_difficulty(meta)
        assert assessment.score >= 3

    def test_assessment_has_all_fields(self):
        meta = self._meta(status_code=200)
        a = self.engine.assess_difficulty(meta)
        assert isinstance(a, DifficultyAssessment)
        assert 1 <= a.score <= 5
        assert a.recommended_tool in ("general_scrape", "dynamic_scrape", "pdf_extract", "alternative_source")
        assert isinstance(a.notes, str)


class TestSourceRanking:
    def setup_method(self):
        self.engine = StrategyEngine()

    def test_financial_sites_ranked_above_generic(self):
        results = [
            {"url": "https://en.wikipedia.org/wiki/S%26P_500", "title": "S&P 500 - Wikipedia", "snippet": "", "domain": "en.wikipedia.org"},
            {"url": "https://www.macrotrends.net/2526/sp-500-historical", "title": "S&P 500 History", "snippet": "", "domain": "macrotrends.net"},
            {"url": "https://slickcharts.com/sp500", "title": "S&P 500 SlickCharts", "snippet": "", "domain": "slickcharts.com"},
        ]
        ranked = self.engine.rank_sources(results, goal="S&P 500 historical returns")
        urls = [r["url"] for r in ranked]
        wiki_idx = next(i for i, u in enumerate(urls) if "wikipedia" in u)
        assert wiki_idx > 0  # wikipedia should not be first

    def test_ranking_preserves_all_results(self):
        results = [
            {"url": "https://a.com", "title": "A", "snippet": "", "domain": "a.com"},
            {"url": "https://b.com", "title": "B", "snippet": "", "domain": "b.com"},
        ]
        ranked = self.engine.rank_sources(results, goal="test")
        assert len(ranked) == len(results)

    def test_empty_results_returns_empty(self):
        assert self.engine.rank_sources([], goal="test") == []


class TestFallbackSuggestions:
    def setup_method(self):
        self.engine = StrategyEngine()

    def _state_with_attempts(self, attempts: list[ScrapeAttempt]) -> AgentState:
        state = AgentState(goal="test goal")
        for a in attempts:
            state.record_attempt(a)
        return state

    def test_js_failure_suggests_dynamic_scrape(self):
        state = self._state_with_attempts([
            ScrapeAttempt(loop=1, url="https://example.com", tool_used="general_scrape",
                          blocking_issues=["is_js_required"])
        ])
        suggestion = self.engine.suggest_fallback(state)
        assert "dynamic_scrape" in suggestion.lower()

    def test_cloudflare_suggests_alternative_or_api(self):
        state = self._state_with_attempts([
            ScrapeAttempt(loop=1, url="https://example.com", tool_used="general_scrape",
                          blocking_issues=["cloudflare"]),
            ScrapeAttempt(loop=2, url="https://example.com", tool_used="dynamic_scrape",
                          blocking_issues=["cloudflare"]),
        ])
        suggestion = self.engine.suggest_fallback(state)
        assert suggestion  # some non-empty suggestion

    def test_many_failures_recommends_user_intervention(self):
        attempts = [
            ScrapeAttempt(loop=i, url=f"https://site{i}.com", tool_used="general_scrape",
                          result_quality=0.0)
            for i in range(6)
        ]
        state = self._state_with_attempts(attempts)
        suggestion = self.engine.suggest_fallback(state)
        assert "user" in suggestion.lower() or "intervention" in suggestion.lower() or "alternative" in suggestion.lower()


class TestDomainCooldown:
    def setup_method(self):
        self.engine = StrategyEngine()

    def test_fresh_domain_not_on_cooldown(self):
        assert self.engine.is_on_cooldown("https://example.com") is False

    def test_domain_on_cooldown_after_record(self):
        self.engine.record_request("https://example.com/data")
        assert self.engine.is_on_cooldown("https://example.com/other", cooldown_seconds=10) is True

    def test_cooldown_expires(self):
        self.engine.record_request("https://example.com/data")
        assert self.engine.is_on_cooldown("https://example.com/other", cooldown_seconds=0) is False

    def test_different_domain_not_affected(self):
        self.engine.record_request("https://site-a.com/page")
        assert self.engine.is_on_cooldown("https://site-b.com/page", cooldown_seconds=10) is False
