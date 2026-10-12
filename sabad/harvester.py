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
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.matcher import (
    match_sku,
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
                logger.error(f"Error fetching flash deals from {s_name}: {result}")
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
            s_name: adapter.get_store_info(lat, lng)
            for s_name, adapter in self.adapters.items()
        }
        store_info_results = await asyncio.gather(
            *store_info_tasks.values(), return_exceptions=True
        )

        store_infos: Dict[str, StoreInfo] = {}
        for (s_name, _), res in zip(store_info_tasks.items(), store_info_results):
            if isinstance(res, Exception):
                logger.error(f"Error fetching store info for {s_name}: {res}")
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
                search_coroutines.append(adapter.search(search_query, lat, lng))

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
        for (raw_text, s_name, _), candidates_or_err in zip(search_keys, search_results):
            if isinstance(candidates_or_err, Exception):
                logger.error(f"Search error for '{raw_text}' on {s_name}: {candidates_or_err}")
                cands_by_item_store[raw_text][s_name] = []
            else:
                cands_by_item_store[raw_text][s_name] = candidates_or_err

        for item_obj in basket_items:
            raw_text = item_obj.raw_text
            store_cands = cands_by_item_store[raw_text]

            # If user explicitly specified volume or pack size, match directly per store
            if item_obj.volume_weight is not None:
                for s_name, cands in store_cands.items():
                    catalog_matches[raw_text][s_name] = match_sku(item_obj, cands)
                continue

            # User did NOT specify volume/size: harmonize variants across stores
            # ponytail: Harmonize unconstrained queries to maximize identical cross-store variant coverage.
            bucket_store_coverage: Dict[str, set] = {}
            for s_name, cands in store_cands.items():
                s_buckets = set()
                for c in cands:
                    if not c.is_in_stock or not is_product_type_compatible(item_obj.name, c.title):
                        continue
                    if not is_flavor_compatible(f"{item_obj.name} {raw_text}", c.title):
                        continue
                    if not is_fat_compatible(item_obj.fat_percentage, c.title):
                        continue
                    if item_obj.brand and item_obj.brand not in clean_persian_text(f"{c.title} {c.brand or ''}"):
                        continue
                    b = extract_size_bucket(c.title)
                    s_buckets.add(b)
                for b in s_buckets:
                    bucket_store_coverage.setdefault(b, set()).add(s_name)

            preferred_buckets = {
                "مایع دستشویی": ["vol_small", "vol_standard", "vol_family", "vol_bulk"],
                "مایع ظرفشویی": ["vol_standard", "vol_small", "vol_family", "vol_bulk"],
                "دستمال توالت": ["count_4", "count_2", "count_8", "count_12"],
                "شیر": ["vol_standard", "vol_family", "vol_small"],
                "پنیر": ["vol_small", "vol_standard"],
            }
            pref_list = preferred_buckets.get(item_obj.name, [])

            def bucket_priority(b: str) -> Tuple[int, int]:
                store_count = len(bucket_store_coverage.get(b, set()))
                pref_idx = pref_list.index(b) if b in pref_list else 99
                return (store_count, -pref_idx)

            valid_buckets = {k: v for k, v in bucket_store_coverage.items() if k != "unknown"}
            if valid_buckets:
                best_bucket = max(valid_buckets.keys(), key=bucket_priority)
                for s_name, cands in store_cands.items():
                    filtered = [
                        c for c in cands
                        if extract_size_bucket(c.title) == best_bucket
                    ]
                    catalog_matches[raw_text][s_name] = match_sku(item_obj, filtered)
            else:
                for s_name, cands in store_cands.items():
                    catalog_matches[raw_text][s_name] = match_sku(item_obj, cands)

        return store_infos, catalog_matches
