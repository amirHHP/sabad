"""Week-over-week price history and fake-discount detection."""

from datetime import datetime, timedelta, timezone

from sabad.durable_store import MemoryEventLog, RedisEventLog
from sabad.models.catalog import StoreItem
from sabad.price_history import PriceHistoryStore


def _item(price: float, base: float, percent: float = 0) -> StoreItem:
    return StoreItem(
        platform="okala",
        store_id="branch",
        product_id="shampoo-400",
        title="شامپو سر ۴۰۰ میلی‌لیتری",
        base_price=base,
        discount_price=price,
        discount_percent=percent,
        is_in_stock=True,
    )


def _store(tmp_path):
    return PriceHistoryStore(path=str(tmp_path / "prices.sqlite3"))


def test_same_day_repeat_is_not_treated_as_last_week(tmp_path):
    store = _store(tmp_path)
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    first = store.record([_item(140_000, 140_000)], captured_at=now.isoformat())
    second = store.record([_item(140_000, 140_000)], captured_at=(now + timedelta(hours=2)).isoformat())

    assert first["okala:shampoo-400"].verdict == "no_history"
    assert second["okala:shampoo-400"].verdict == "no_history"
    store.close()


def test_lower_selling_price_is_a_real_discount(tmp_path):
    store = _store(tmp_path)
    today = datetime(2026, 10, 28, tzinfo=timezone.utc)
    store.record([_item(140_000, 140_000)], captured_at=(today - timedelta(days=7)).isoformat())
    change = store.record([_item(110_000, 140_000, percent=21)], captured_at=today.isoformat())
    result = change["okala:shampoo-400"]

    assert result.verdict == "real_discount"
    assert result.week_ago_price == 140_000
    assert "ارزان‌تر" in result.label
    store.close()


def test_raised_list_price_with_same_selling_price_is_makeup(tmp_path):
    store = _store(tmp_path)
    today = datetime(2026, 10, 28, tzinfo=timezone.utc)
    store.record([_item(140_000, 140_000)], captured_at=(today - timedelta(days=8)).isoformat())
    change = store.record([_item(140_000, 200_000, percent=30)], captured_at=today.isoformat())
    result = change["okala:shampoo-400"]

    assert result.verdict == "price_makeup"
    assert "برچسب" in result.label
    store.close()


def test_redis_log_keeps_the_same_week_comparison():
    class FakeRedis:
        def __init__(self):
            self.lists = {}

        def rpush(self, key, value):
            self.lists.setdefault(key, []).append(value)
            return len(self.lists[key])

        def ltrim(self, key, start, end):
            rows = self.lists.get(key, [])
            self.lists[key] = rows[start:] if end == -1 else rows[start : end + 1]

        def lrange(self, key, start, end):
            rows = self.lists.get(key, [])
            if end == -1:
                end = len(rows) - 1
            if start < 0:
                start = max(len(rows) + start, 0)
            return rows[start : end + 1]

    store = PriceHistoryStore(log=RedisEventLog(FakeRedis()))
    today = datetime(2026, 10, 28, tzinfo=timezone.utc)
    store.record([_item(90_000, 90_000)], captured_at=(today - timedelta(days=7)).isoformat())
    change = store.record([_item(120_000, 120_000)], captured_at=today.isoformat())

    assert change["okala:shampoo-400"].verdict == "increase"
    assert change["okala:shampoo-400"].delta == 30_000


def test_memory_log_is_used_when_no_path_is_required():
    store = PriceHistoryStore(log=MemoryEventLog())
    change = store.record([_item(10_000, 10_000)], captured_at="2026-10-28T00:00:00+00:00")
    assert change["okala:shampoo-400"].verdict == "no_history"
