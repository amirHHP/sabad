"""API authentication, rate limits, secret redaction, and per-store timeouts."""

from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.testclient import TestClient

from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.harvester import CatalogHarvester
from sabad.models.catalog import DeliveryTier, StoreInfo, StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import OptimizationResult
from sabad.price_history import PriceHistoryStore
from sabad.security import SlidingWindowLimiter, log_store_failure, redact_secrets
from sabad import http_api


def test_redact_secrets_hides_tokens_and_gemini_keys():
    raw = "failed token=abc123 secret=hunter2 url=https://example.test/v1?key=AIzaSyabcdefghijklmnopqrstuvwxyz"
    cleaned = redact_secrets(raw)
    assert "abc123" not in cleaned
    assert "hunter2" not in cleaned
    assert "AIzaSy" not in cleaned
    assert "[redacted]" in cleaned


def test_log_store_failure_does_not_emit_the_secret(caplog):
    caplog.set_level("WARNING")
    log_store_failure("okala", "search", RuntimeError("authorization: Bearer super-secret-token"))
    assert "super-secret-token" not in caplog.text
    assert "okala" in caplog.text


def test_sliding_window_blocks_the_extra_search():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.allow("shopper")[0] is True
    allowed, retry_after = limiter.allow("shopper")
    assert allowed is False
    assert retry_after >= 1


@pytest.mark.asyncio
async def test_search_timeout_is_recorded_for_the_shopper(monkeypatch):
    async def hang(*_args, **_kwargs):
        raise TimeoutError("slow store")

    adapter = AsyncMock()
    adapter.platform_title_fa = "اکالا"
    adapter.search = hang
    adapter.get_store_info.return_value = StoreInfo(
        platform="okala",
        store_id="branch",
        title="اکالا",
        delivery_tiers=[DeliveryTier(min_subtotal=0, fee=0)],
    )
    monkeypatch.setattr("sabad.harvester.HTTP_TIMEOUT", 1)
    harvester = CatalogHarvester({"okala": adapter})
    item = ParsedGroceryItem(raw_text="شامپو", name="شامپو")

    _infos, matches = await harvester.harvest_catalog_matches([item], 35.7, 51.4)
    evidence = harvester.last_search_evidence["شامپو"]["okala"]

    assert matches["شامپو"]["okala"] is None
    assert evidence["error"] == "timeout"
    assert any(attempt["error"] == "timeout" for attempt in evidence["queries"])


@pytest.mark.asyncio
async def test_snapp_search_timeout_propagates():
    adapter = SnappMarketAdapter()

    async def boom(*_args, **_kwargs):
        raise httpx.ReadTimeout("timed out")

    adapter.client.get = boom
    with pytest.raises(httpx.ReadTimeout):
        await adapter.search("شامپو", 35.7, 51.4)
    await adapter.client.aclose()


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("SABAD_API_KEY", "test-key")
    monkeypatch.delenv("SABAD_ENV", raising=False)
    monkeypatch.setattr(http_api, "_compare_limiter", SlidingWindowLimiter(limit=5, window_seconds=60))
    monkeypatch.setattr(http_api, "_feedback_limiter", SlidingWindowLimiter(limit=5, window_seconds=60))
    monkeypatch.setattr(http_api, "history_store", lambda: PriceHistoryStore(path=str(tmp_path / "prices.sqlite3")))
    from sabad.feedback import FeedbackStore

    monkeypatch.setattr(http_api, "feedback_store", lambda: FeedbackStore(path=str(tmp_path / "feedback.sqlite3")))
    return TestClient(http_api.create_app())


def test_vercel_without_api_key_is_rejected(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("SABAD_ENV", raising=False)
    monkeypatch.delenv("SABAD_API_KEY", raising=False)
    client = TestClient(http_api.create_app())
    response = client.post("/api/v1/compare", json={"text": "شامپو"})
    assert response.status_code == 503


def test_production_without_api_key_is_rejected(monkeypatch):
    monkeypatch.setenv("SABAD_ENV", "production")
    monkeypatch.delenv("SABAD_API_KEY", raising=False)
    client = TestClient(http_api.create_app())
    response = client.post("/api/v1/compare", json={"text": "شامپو"})
    assert response.status_code == 503
    assert "test-key" not in response.text
    assert "GEMINI" not in response.text


def test_compare_requires_the_configured_key(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post("/api/v1/compare", json={"text": "شامپو"})
    assert response.status_code == 401


def test_compare_returns_unit_price_without_leaking_errors(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    item = StoreItem(
        platform="snapp_market",
        store_id="branch",
        product_id="s1000",
        title="شامپو سر ۱۰۰۰ میلی‌لیتری",
        base_price=280_000,
        discount_price=240_000,
        is_in_stock=True,
    )

    class Adapter:
        platform_title_fa = "اسنپ‌مارکت"

    class Harvester:
        adapters = {"snapp_market": Adapter()}
        last_search_evidence = {
            "شامپو": {
                "snapp_market": {
                    "candidate_count": 3,
                    "selected": item.title,
                    "selected_in_stock": True,
                    "unit_options": [
                        {"product_id": "s1000", "title": item.title, "unit_price": 24000, "text": "24,000 تومان / هر ۱۰۰ میلی‌لیتر", "is_cheapest": True}
                    ],
                }
            }
        }

    async def fake_compare(*_args, **_kwargs):
        return (
            Harvester(),
            {},
            {"شامپو": {"snapp_market": item}},
            {},
            OptimizationResult(total_items_cost=240_000, grand_total_cost=240_000),
        )

    monkeypatch.setattr(http_api, "compare_and_optimize_basket", fake_compare)
    response = client.post(
        "/api/v1/compare",
        json={"text": "شامپو", "latitude": 35.7, "longitude": 51.4},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    body = response.json()
    line = body["stores"][0]["lines"][0]
    assert line["in_stock"] is True
    assert "۱۰۰" in line["unit_price_text"] or "100" in line["unit_price_text"]
    assert "AIza" not in response.text
    assert body["optimal_total"] == 240_000


def test_compare_failure_response_redacts_the_exception(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    async def explode(*_args, **_kwargs):
        raise RuntimeError("upstream token=super-secret-token")

    monkeypatch.setattr(http_api, "compare_and_optimize_basket", explode)
    response = client.post(
        "/api/v1/compare",
        json={"text": "شامپو"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 502
    assert "super-secret-token" not in response.text


def test_search_limit_is_counted_per_browser(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(http_api, "_compare_limiter", SlidingWindowLimiter(limit=1, window_seconds=60))

    async def fake_compare(*_args, **_kwargs):
        return (
            type("Harvester", (), {"adapters": {}, "last_search_evidence": {}})(),
            {},
            {},
            {},
            OptimizationResult(total_items_cost=0, grand_total_cost=0),
        )

    monkeypatch.setattr(http_api, "compare_and_optimize_basket", fake_compare)
    headers = {"Authorization": "Bearer test-key"}
    first = client.post("/api/v1/compare", json={"text": "شامپو"}, headers={**headers, "X-Sabad-Client": "10.0.0.1"})
    second = client.post("/api/v1/compare", json={"text": "شامپو"}, headers={**headers, "X-Sabad-Client": "10.0.0.2"})
    third = client.post("/api/v1/compare", json={"text": "شامپو"}, headers={**headers, "X-Sabad-Client": "10.0.0.1"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_feedback_endpoint_accepts_only_known_reasons(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    headers = {"Authorization": "Bearer test-key"}
    bad = client.post("/api/v1/feedback", json={"reason": "سایر", "title": "حوله ورزشی"}, headers=headers)
    assert bad.status_code == 400
    good = client.post(
        "/api/v1/feedback",
        json={"reason": "محصول خودرو", "title": "واکس خودرو", "requested": "واکس", "platform": "okala"},
        headers=headers,
    )
    assert good.status_code == 200
    assert good.json()["ok"] is True


def test_production_session_is_not_written_to_a_local_file(monkeypatch, tmp_path):
    from sabad.adapters.session_manager import SessionManager

    monkeypatch.setenv("SABAD_ENV", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(SessionManager, "_get_streamlit_session_state", classmethod(lambda cls: None))
    monkeypatch.setattr("sabad.adapters.session_manager.SESSIONS_DIR", tmp_path)

    SessionManager.save_tokens("snapp_market", "token-value-123456", phone="09120000000")
    assert list(tmp_path.glob("*.json")) == []
    assert SessionManager.get_token("snapp_market") is None
