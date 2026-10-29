"""Price history used to tell a real discount from a raised list price.

Observations live in SQLite locally and in Redis when ``REDIS_URL`` is set.
A comparison uses the latest price that is at least six days old, so two
searches on the same day are not treated as a week of history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional

from sabad.durable_store import EventLog, open_event_log
from sabad.models.catalog import StoreItem
from sabad.pricing import comparable_price


@dataclass(frozen=True)
class PriceChange:
    current_price: float
    previous_price: Optional[float]
    delta: Optional[float]
    captured_at: str
    week_ago_price: Optional[float]
    base_price: float
    week_ago_base: Optional[float]
    verdict: str
    label: str


def describe_price_change(
    *,
    current_price: float,
    current_base: float,
    week_price: Optional[float],
    week_base: Optional[float],
    discount_percent: float,
    captured_at: str,
) -> PriceChange:
    """Classify today's selling price against the price recorded a week ago."""
    shows_discount = discount_percent >= 10 or (
        current_base > 0 and current_price > 0 and current_base > current_price * 1.08
    )
    base_inflated = (
        week_base is not None
        and week_base > 0
        and current_base > week_base * 1.05
    )
    if week_price is None or week_price <= 0:
        verdict = "no_history"
        label = "برای مقایسه با هفتهٔ قبل هنوز قیمت قدیمی‌تری ثبت نشده."
        delta = None
    elif current_price < week_price * 0.98:
        verdict = "real_discount"
        delta = current_price - week_price
        label = f"نسبت به هفتهٔ قبل {abs(delta):,.0f} تومان ارزان‌تر شده."
    elif shows_discount and current_price >= week_price * 0.98 and (base_inflated or current_base > current_price * 1.08):
        verdict = "price_makeup"
        delta = current_price - week_price
        label = "تخفیف روی برچسب است؛ قیمت فروش نسبت به هفتهٔ قبل کمتر نشده."
    elif current_price > week_price * 1.02:
        verdict = "increase"
        delta = current_price - week_price
        label = f"نسبت به هفتهٔ قبل {delta:,.0f} تومان گران‌تر شده."
    else:
        verdict = "unchanged"
        delta = current_price - week_price
        label = "قیمت فروش نسبت به هفتهٔ قبل تقریباً ثابت است."

    return PriceChange(
        current_price=float(current_price),
        previous_price=week_price,
        delta=delta,
        captured_at=captured_at,
        week_ago_price=week_price,
        base_price=float(current_base),
        week_ago_base=week_base,
        verdict=verdict,
        label=label,
    )


class PriceHistoryStore:
    """Record selected SKUs and compare them with last week's observation."""

    def __init__(self, path: Optional[str] = None, log: Optional[EventLog] = None):
        self._log = log or open_event_log("price_history.sqlite3", path)

    @staticmethod
    def item_key(item: StoreItem) -> str:
        identity = item.product_id or item.title
        return f"{item.platform}:{identity}"

    def _week_row(self, key: str, now: datetime) -> Optional[dict]:
        cutoff = (now - timedelta(days=6)).isoformat()
        chosen = None
        for row in self._log.read("prices", key):
            captured = str(row.get("captured_at") or "")
            if captured and captured <= cutoff:
                chosen = row
        return chosen

    def record(self, items: Iterable[StoreItem], captured_at: Optional[str] = None) -> Dict[str, PriceChange]:
        now = datetime.now(timezone.utc) if captured_at is None else datetime.fromisoformat(captured_at)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        stamp = now.isoformat()
        changes: Dict[str, PriceChange] = {}
        for item in items:
            if not item.is_in_stock or item.discount_price <= 0:
                continue
            key = self.item_key(item)
            previous = self._week_row(key, now)
            week_price = float(previous["price"]) if previous and previous.get("price") is not None else None
            week_base = float(previous["base_price"]) if previous and previous.get("base_price") is not None else None
            change = describe_price_change(
                current_price=float(item.discount_price),
                current_base=float(item.base_price or item.discount_price),
                week_price=week_price,
                week_base=week_base,
                discount_percent=float(item.discount_percent or 0),
                captured_at=stamp,
            )
            changes[key] = change
            unit = comparable_price(item)
            self._log.append(
                "prices",
                key,
                {
                    "item_key": key,
                    "platform": item.platform,
                    "product_id": item.product_id or "",
                    "title": item.title,
                    "price": float(item.discount_price),
                    "base_price": float(item.base_price or item.discount_price),
                    "unit_price": unit.value if unit else None,
                    "captured_at": stamp,
                },
            )
        return changes

    def record_matches(self, catalog_matches: dict) -> Dict[str, PriceChange]:
        selected: list[StoreItem] = []
        seen: set[str] = set()
        for store_matches in (catalog_matches or {}).values():
            for item in (store_matches or {}).values():
                if item is None:
                    continue
                key = self.item_key(item)
                if key not in seen:
                    seen.add(key)
                    selected.append(item)
        return self.record(selected)

    def close(self) -> None:
        self._log.close()
