"""Tests for base tool interfaces and data models."""

import pytest
from agent.tools.base import ToolResult, ScrapeMetadata


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, data={"rows": [1, 2, 3]})
        assert r.success is True
        assert r.data == {"rows": [1, 2, 3]}
        assert r.error is None
        assert r.metadata == {}

    def test_failure_result(self):
        r = ToolResult(success=False, data=None, error="Timeout after 30s")
        assert r.success is False
        assert r.error == "Timeout after 30s"

    def test_metadata_stored(self):
        r = ToolResult(success=True, data=None, metadata={"url": "http://example.com", "status_code": 200})
        assert r.metadata["status_code"] == 200

    def test_data_can_be_list(self):
        r = ToolResult(success=True, data=[{"a": 1}, {"a": 2}])
        assert len(r.data) == 2

    def test_data_can_be_string(self):
        r = ToolResult(success=True, data="some text content")
        assert isinstance(r.data, str)


class TestScrapeMetadata:
    def test_defaults(self):
        m = ScrapeMetadata(url="https://example.com")
        assert m.status_code == 0
        assert m.has_captcha is False
        assert m.has_cloudflare is False
        assert m.is_js_required is False
        assert m.content_length == 0
        assert m.response_time_ms == 0.0

    def test_cloudflare_flagged(self):
        m = ScrapeMetadata(url="https://example.com", has_cloudflare=True, status_code=403)
        assert m.has_cloudflare is True
        assert m.status_code == 403

    def test_captcha_flagged(self):
        m = ScrapeMetadata(url="https://example.com", has_captcha=True)
        assert m.has_captcha is True

    def test_js_required_flagged(self):
        m = ScrapeMetadata(url="https://example.com", is_js_required=True)
        assert m.is_js_required is True

    def test_full_metadata(self):
        m = ScrapeMetadata(
            url="https://example.com/data",
            status_code=200,
            content_type="text/html",
            content_length=45000,
            has_captcha=False,
            has_cloudflare=False,
            is_js_required=False,
            response_time_ms=312.5,
        )
        assert m.content_type == "text/html"
        assert m.content_length == 45000
        assert m.response_time_ms == 312.5
