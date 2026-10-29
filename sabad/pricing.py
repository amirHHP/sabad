"""Comparable price calculations for catalog results.

Retailers sell the same everyday item in different pack sizes.  This module
keeps the displayed selling price in tomans while also exposing a comparable
price per 100 g/ml or per piece.  Unknown sizes deliberately return ``None``
instead of guessing.
"""

from dataclasses import dataclass
from typing import Optional

from sabad.models.catalog import StoreItem
from sabad.normalizer.matcher import extract_volume_from_title


@dataclass(frozen=True)
class ComparablePrice:
    value: float
    label: str
    quantity: float
    unit: str


def comparable_price(item: StoreItem) -> Optional[ComparablePrice]:
    """Return a normalized selling price for a known pack size."""
    quantity, unit = extract_volume_from_title(item.title or "")
    if quantity is None or unit is None or quantity <= 0 or item.discount_price <= 0:
        return None

    normalized_unit = unit.replace(" ", "").replace("\u200c", "")
    if normalized_unit in {"عدد", "تایی", "عددی", "رول", "قلو", "برگ"}:
        return ComparablePrice(
            value=item.discount_price / quantity,
            label="هر عدد",
            quantity=quantity,
            unit="عدد",
        )

    if normalized_unit in {"میلیلیتر", "سیسی", "میل", "میلی"}:
        base_quantity = quantity
        label = "هر ۱۰۰ میلی‌لیتر"
    elif normalized_unit == "لیتر":
        base_quantity = quantity * 1000.0
        label = "هر ۱۰۰ میلی‌لیتر"
    elif normalized_unit == "کیلوگرم":
        base_quantity = quantity * 1000.0
        label = "هر ۱۰۰ گرم"
    elif normalized_unit == "گرم":
        base_quantity = quantity
        label = "هر ۱۰۰ گرم"
    else:
        return None

    return ComparablePrice(
        value=(item.discount_price / base_quantity) * 100.0,
        label=label,
        quantity=quantity,
        unit=normalized_unit,
    )


def comparable_price_text(item: StoreItem) -> Optional[str]:
    """Format a normalized price for compact Persian UI cards."""
    price = comparable_price(item)
    if price is None:
        return None
    return f"{price.value:,.0f} تومان / {price.label}"


# Packs at or above this size (ml or g) are bulk. A 4L jug must not beat a
# bottle only because its price per 100ml is lower.
_BULK_BASE = 1800.0


def _pack_base(price: ComparablePrice) -> float:
    if price.unit in {"لیتر", "کیلوگرم"}:
        return price.quantity * 1000.0
    return price.quantity


def comparison_rank_key(item: StoreItem) -> tuple[int, float, float]:
    """Rank everyday packs by comparable unit price and keep bulk packs behind them.

    The first element is a tier: 0 everyday, 1 bulk, 2 unknown size. Lower is
    better. Inside a tier, the next number is the comparable unit price, then
    the pack price.
    """
    pack = item.discount_price if item.discount_price > 0 else float("inf")
    priced = comparable_price(item)
    if priced is None:
        return (2, pack, pack)
    if priced.unit != "عدد" and _pack_base(priced) >= _BULK_BASE:
        return (1, pack, priced.value)
    return (0, priced.value, pack)


def everyday_comparison_value(item: StoreItem) -> float:
    """Value used to choose a shared size family across stores."""
    priced = comparable_price(item)
    if priced is None or item.discount_price <= 0:
        return float("inf")
    if priced.unit != "عدد" and _pack_base(priced) >= _BULK_BASE:
        return item.discount_price
    return priced.value


def unit_price_options(items: list[StoreItem]) -> list[dict]:
    """List in-stock packs that can be compared, cheapest unit price first."""
    rows = []
    for item in items:
        priced = comparable_price(item)
        if priced is None or not item.is_in_stock or item.discount_price <= 0:
            continue
        rows.append(
            {
                "title": item.title,
                "product_id": item.product_id,
                "pack_price": float(item.discount_price),
                "unit_price": round(priced.value, 2),
                "unit_label": priced.label,
                "text": f"{priced.value:,.0f} تومان / {priced.label}",
            }
        )
    if not rows:
        return []
    best = min(row["unit_price"] for row in rows)
    for row in rows:
        row["is_cheapest"] = row["unit_price"] == best
    rows.sort(key=lambda row: (row["unit_price"], row["pack_price"], row["title"]))
    return rows

