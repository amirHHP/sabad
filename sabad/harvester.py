"""
Live Flash Deal & Catalog Harvester for Sabad.
Executes concurrent network requests across SnappMarket, Digikala Jet, and Okala.
"""

import asyncio
import logging
import re
from typing import Dict, List, Tuple, Optional

from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.tapsi_market import TapsiMarketAdapter
from sabad.config import HTTP_TIMEOUT
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.pricing import everyday_comparison_value, unit_price_options
from sabad.security import log_store_failure
from sabad.normalizer.matcher import (
    match_sku,
    explain_sku_candidates,
    is_flavor_compatible,
    is_product_type_compatible,
    is_fat_compatible,
)
from sabad.normalizer.persian_digits import clean_persian_text

logger = logging.getLogger(__name__)


def extract_size_bucket(title: str) -> str:
    """Classifies catalog SKU title into a canonical size bucket for cross-store harmonization."""
    cleaned = title.replace('٫', '.').replace('/', '.')

    # 1. Pack / Roll / Sheet count
    m_count = re.search(r'(\d+)\s*(?:عددی|تایی|قلو|رول|برگ)', cleaned)
    if m_count:
        cnt = int(m_count.group(1))
        unit = 'sheet' if 'برگ' in m_count.group(0) else 'count'
        return f'{unit}_{cnt}'

    verbal_counts = [
        (r'دو\s*(?:قلو|رول)', 2),
        (r'چهار\s*(?:قلو|رول)', 4),
        (r'شش\s*(?:قلو|رول)', 6),
        (r'هشت\s*(?:قلو|رول)', 8),
        (r'دوازده\s*(?:قلو|رول)', 12),
    ]
    for pat, val in verbal_counts:
        if re.search(pat, cleaned):
            return f'count_{val}'

    # 2. Volume / Weight buckets
    number_re = r'(\d+(?:[./٫]\d+)?)'
    unit_re = (
        r'(میلی\s*لیتری|میلی\s*لیتر|میلی|میل|سی\s*سی|سی‌سی|'
        r'کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو|'
        r'لیتری|لیتر|گرمی|گرم)'
    )
    m_vol = re.search(rf'{number_re}\s*{unit_re}', cleaned)
    if m_vol:
        val = float(m_vol.group(1))
        u = m_vol.group(2)
        if any(x in u for x in ['کیلو', 'لیتر']) and not any(x in u for x in ['میلی', 'میل']):
            base_g = val * 1000.0
        elif val < 10.0 and ('گرم' in u):
            # Upstream typo guard: e.g. 3.75 گرمی for detergents is 3.75 kg
            base_g = val * 1000.0
        else:
            base_g = val
        if base_g < 750:
            return 'vol_small'      # e.g. 200ml, 350g, 400ml, 450g, 500g
        elif base_g < 1800:
            return 'vol_standard'   # e.g. 900g, 1L, 1kg, 1.5L
        elif base_g < 3000:
            return 'vol_family'     # e.g. 2kg, 2.5kg
        else:
            return 'vol_bulk'       # e.g. 3.75kg, 4L, 5kg

    return 'unknown'


class CatalogHarvester:
    """
    Concurrent harvester for multi-store catalog search and daily flash deals.
    """

    def __init__(self, adapters: Optional[Dict[str, BaseStoreAdapter]] = None):
        self.adapters = adapters or {
            "snapp_market": SnappMarketAdapter(),
            "digikala_jet": DigikalaJetAdapter(),
            "okala": OkalaAdapter(),
            "tapsi_market": TapsiMarketAdapter(),
        }
        # Per-run, user-visible evidence. This is deliberately kept on the
        # request-scoped harvester and copied to Streamlit session state.
        self.last_search_evidence: Dict[str, Dict[str, dict]] = {}

    @staticmethod
    def _query_variants(item: ParsedGroceryItem) -> List[str]:
        """Build precise fallbacks without changing the user's requested item."""
        base = f"{item.name} {item.brand or ''}".strip()
        raw = clean_persian_text(item.raw_text)
        variants = [base, raw]
        synonyms = {
            "شامپو": ["شامپو", "شامپو سر", "شامپو مو", "شامپو کوچک"],
            "حوله": ["حوله", "حوله دستی", "حوله کوچک"],
            "واکس": ["واکس", "واکس کفش", "واکس کفش کوچک"],
            "تخم مرغ": ["تخم مرغ", "تخم‌مرغ", "تخم مرغ بسته"],
            "ماکارونی": ["ماکارونی", "پاستا"],
            "پاستا": ["پاستا", "ماکارونی"],
            "پتی بور": ["پتی بور", "پتیبور", "بیسکویت پتی بور"],
            "پنیر ماسکارپونه": ["پنیر ماسکارپونه", "ماسکارپونه"],
            "پودر کاکائو": ["پودر کاکائو", "کاکائو"],
        }
        variants.extend(synonyms.get(item.name, []))
        result: List[str] = []
        for variant in variants:
            normalized = clean_persian_text(variant).strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result[:4]

    async def _search_item_store(
        self,
        item: ParsedGroceryItem,
        store_name: str,
        adapter: BaseStoreAdapter,
        lat: float,
        lng: float,
    ) -> Tuple[List[StoreItem], dict]:
        """Search once, then broaden only when the first response cannot match."""
        queries = self._query_variants(item)
        merged: List[StoreItem] = []
        seen_ids = set()
        attempts = []

        for query in queries:
            try:
                response = await asyncio.wait_for(adapter.search(query, lat, lng), timeout=HTTP_TIMEOUT)
                response = response or []
                for candidate in response:
                    candidate_id = candidate.product_id or f"{candidate.title}:{candidate.discount_price}"
                    if candidate_id not in seen_ids:
                        seen_ids.add(candidate_id)
                        merged.append(candidate)
                attempts.append({"query": query, "result_count": len(response), "error": None})
            except TimeoutError:
                log_store_failure(store_name, "search", TimeoutError(query))
                attempts.append({"query": query, "result_count": 0, "error": "timeout"})
            except Exception as exc:
                log_store_failure(store_name, "search", exc)
                attempts.append({"query": query, "result_count": 0, "error": type(exc).__name__})

            # For an explicitly sized request one compatible SKU is enough.
            # For a generic request (e.g. «شامپو») keep all query variants so
            # the cheapest comparable size can win instead of the first,
            # often oversized, API result.
            if item.volume_weight is not None:
                if match_sku(item, [c for c in merged if c.is_in_stock]):
                    break

        evidence = explain_sku_candidates(item, merged)
        evidence.update({
            "requested": item.display_title,
            "queries": attempts,
            "selected": None,
        })
        if not merged and any(attempt.get("error") == "timeout" for attempt in attempts):
            evidence["error"] = "timeout"
        elif not merged and any(attempt.get("error") for attempt in attempts):
            evidence["error"] = next(attempt["error"] for attempt in reversed(attempts) if attempt.get("error"))
        return merged, evidence

    async def harvest_flash_deals(
        self, lat: float, lng: float
    ) -> Dict[str, List[StoreItem]]:
        """
        Scans active daily flash deals across all connected platforms concurrently.
        """
        tasks = {
            s_name: adapter.get_flash_deals(lat, lng)
            for s_name, adapter in self.adapters.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        deals_by_store: Dict[str, List[StoreItem]] = {}

        for (s_name, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                log_store_failure(s_name, "flash_deals", result)
                deals_by_store[s_name] = []
            else:
                deals_by_store[s_name] = result

        return deals_by_store

    async def harvest_catalog_matches(
        self,
        basket_items: List[ParsedGroceryItem],
        lat: float,
        lng: float,
    ) -> Tuple[Dict[str, StoreInfo], Dict[str, Dict[str, Optional[StoreItem]]]]:
        """
        Concurrently queries store infos and searches product catalogs for all items in the basket.
        Uses asyncio.gather for maximum throughput and low latency.
        """
        # Step 1: Concurrently fetch store info & delivery tiers
        store_info_tasks = {
            s_name: asyncio.wait_for(adapter.get_store_info(lat, lng), timeout=HTTP_TIMEOUT)
            for s_name, adapter in self.adapters.items()
        }
        store_info_results = await asyncio.gather(
            *store_info_tasks.values(), return_exceptions=True
        )

        store_infos: Dict[str, StoreInfo] = {}
        for (s_name, _), res in zip(store_info_tasks.items(), store_info_results):
            if isinstance(res, Exception):
                log_store_failure(s_name, "store_info", res)
                store_infos[s_name] = StoreInfo(
                    platform=s_name,
                    store_id="unknown",
                    title=self.adapters[s_name].platform_title_fa,
                    delivery_tiers=[],
                )
            else:
                store_infos[s_name] = res

        # Step 2: Concurrently query search endpoints for each (item, store) pair
        search_keys: List[Tuple[str, str, ParsedGroceryItem]] = []
        search_coroutines = []

        for item in basket_items:
            search_query = f"{item.name} {item.brand or ''}".strip()
            for s_name, adapter in self.adapters.items():
                search_keys.append((item.raw_text, s_name, item))
                search_coroutines.append(self._search_item_store(item, s_name, adapter, lat, lng))

        search_results = await asyncio.gather(
            *search_coroutines, return_exceptions=True
        )

        # Step 3: Match results against parsed criteria with cross-store variant harmonization
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]] = {
            item.raw_text: {} for item in basket_items
        }

        # Index candidates by item and store
        cands_by_item_store: Dict[str, Dict[str, List[StoreItem]]] = {
            item.raw_text: {} for item in basket_items
        }
        self.last_search_evidence = {item.raw_text: {} for item in basket_items}
        for (raw_text, s_name, _), result_or_err in zip(search_keys, search_results):
            if isinstance(result_or_err, Exception):
                log_store_failure(s_name, "search", result_or_err)
                cands_by_item_store[raw_text][s_name] = []
                self.last_search_evidence[raw_text][s_name] = {
                    "requested": raw_text,
                    "queries": [],
                    "candidate_count": 0,
                    "candidate_titles": [],
                    "compatible": [],
                    "rejected": [],
                    "error": type(result_or_err).__name__,
                    "selected": None,
                }
            else:
                candidates, evidence = result_or_err
                cands_by_item_store[raw_text][s_name] = candidates
                self.last_search_evidence[raw_text][s_name] = evidence

        for item_obj in basket_items:
            raw_text = item_obj.raw_text
            store_cands = cands_by_item_store[raw_text]

            # If user explicitly specified volume or pack size, match directly per store
            if item_obj.volume_weight is not None:
                for s_name, cands in store_cands.items():
                    catalog_matches[raw_text][s_name] = match_sku(item_obj, cands)
            else:
                # User did NOT specify volume/size. Pick one comparable size
                # family for the basket first, then choose the cheapest
                # compatible SKU inside that family at every store. This
                # prevents a 4L shampoo jug from beating a 250/400ml bottle
                # just because its title scored higher in fuzzy matching.
                bucket_store_coverage: Dict[str, set] = {}
                bucket_prices: Dict[str, List[float]] = {}
                core_aliases = {
                    "ماکارونی": ("ماکارونی", "پاستا"),
                    "پاستا": ("ماکارونی", "پاستا"),
                    "شامپو": ("شامپو",),
                    "حوله": ("حوله",),
                    "واکس": ("واکس",),
                }

                def is_eligible(candidate: StoreItem) -> bool:
                    if not candidate.is_in_stock:
                        return False
                    candidate_text = clean_persian_text(f"{candidate.title} {candidate.brand or ''}")
                    aliases = core_aliases.get(item_obj.name, (item_obj.name,))
                    if not any(alias in candidate_text for alias in aliases):
                        return False
                    if not is_product_type_compatible(item_obj.name, candidate.title, raw_text):
                        return False
                    if not is_flavor_compatible(f"{item_obj.name} {raw_text}", candidate.title):
                        return False
                    if not is_fat_compatible(item_obj.fat_percentage, candidate.title):
                        return False
                    if item_obj.brand and item_obj.brand not in clean_persian_text(f"{candidate.title} {candidate.brand or ''}"):
                        return False
                    return True

                for s_name, cands in store_cands.items():
                    s_buckets = set()
                    for candidate in cands:
                        if not is_eligible(candidate):
                            continue
                        bucket = extract_size_bucket(candidate.title)
                        if bucket == "unknown":
                            continue
                        s_buckets.add(bucket)
                        if candidate.discount_price > 0:
                            bucket_prices.setdefault(bucket, []).append(everyday_comparison_value(candidate))
                    for bucket in s_buckets:
                        bucket_store_coverage.setdefault(bucket, set()).add(s_name)

                preferred_buckets = {
                    "مایع دستشویی": ["vol_small", "vol_standard", "vol_family", "vol_bulk"],
                    "مایع ظرفشویی": ["vol_standard", "vol_small", "vol_family", "vol_bulk"],
                    "دستمال توالت": ["count_4", "count_2", "count_8", "count_12"],
                    "شیر": ["vol_standard", "vol_family", "vol_small"],
                    "پنیر": ["vol_small", "vol_standard"],
                }
                pref_list = preferred_buckets.get(item_obj.name, [])

                def bucket_priority(bucket: str) -> Tuple[int, int, float]:
                    store_count = len(bucket_store_coverage.get(bucket, set()))
                    pref_idx = pref_list.index(bucket) if bucket in pref_list else 99
                    # When coverage and explicit category preference tie,
                    # choose the lower-priced family (the generic case for
                    # shampoo, pasta, eggs, and similar products).
                    average_price = sum(bucket_prices.get(bucket, [float("inf")])) / max(len(bucket_prices.get(bucket, [])), 1)
                    return (store_count, -pref_idx, -average_price)

                valid_buckets = {k for k in bucket_store_coverage if k != "unknown"}
                everyday_buckets = {
                    bucket for bucket in valid_buckets
                    if bucket in {"vol_small", "vol_standard"} or bucket.startswith(("count_", "sheet_"))
                }
                # A 4L jug is a different purchase from a 200–1000ml bottle.
                # Compare those everyday sizes with each other by unit price,
                # and only fall back to bulk when the store has nothing smaller.
                selection_buckets = everyday_buckets or valid_buckets
                if selection_buckets:
                    best_bucket = max(selection_buckets, key=bucket_priority)
                    covered_stores = bucket_store_coverage[best_bucket]
                    for s_name, cands in store_cands.items():
                        filtered = [
                            candidate for candidate in cands
                            if extract_size_bucket(candidate.title) == best_bucket and is_eligible(candidate)
                        ]
                        if filtered:
                            catalog_matches[raw_text][s_name] = match_sku(item_obj, filtered)
                        else:
                            # Keep a valid result when a store has no SKU in
                            # the shared family; the evidence records that its
                            # local assortment differs instead of declaring the
                            # item absent solely because size was unspecified.
                            catalog_matches[raw_text][s_name] = match_sku(
                                item_obj,
                                [candidate for candidate in cands if is_eligible(candidate)] or cands,
                            )
                            if s_name not in covered_stores:
                                self.last_search_evidence[raw_text][s_name]["size_harmonization"] = (
                                    f"حجم {best_bucket} در این فروشگاه موجود نبود؛ ارزان‌ترین گزینهٔ منطبق نمایش داده شد."
                                )
                else:
                    for s_name, cands in store_cands.items():
                        catalog_matches[raw_text][s_name] = match_sku(item_obj, cands)

            for s_name, selected in catalog_matches[raw_text].items():
                evidence = self.last_search_evidence[raw_text].setdefault(s_name, {})
                visible = [
                    candidate
                    for candidate in cands_by_item_store.get(raw_text, {}).get(s_name, [])
                    if candidate.is_in_stock
                    and is_product_type_compatible(item_obj.name, candidate.title, raw_text)
                ]
                evidence["unit_options"] = unit_price_options(visible)
                evidence["selected"] = selected.title if selected else None
                evidence["selected_in_stock"] = bool(selected and selected.is_in_stock)
                # The final harmonization can filter a title that appeared in
                # the API response. Preserve that fact for the diagnostic UI.
                if selected is None and evidence.get("candidate_count", 0):
                    evidence["final_reason"] = "نتایج برگشتند اما با نوع کالا/حجم/وزن/شباهت نام منطبق نشدند."
                elif selected is None:
                    evidence["final_reason"] = "پاسخ جست‌وجوی این فروشگاه برای این عبارت خالی بود."
                elif not selected.is_in_stock:
                    evidence["final_reason"] = "کالای منطبق پیدا شد اما موجودی شعبه صفر است."
                else:
                    evidence["final_reason"] = "کالای منطبق و موجود پیدا شد."

        return store_infos, catalog_matches
