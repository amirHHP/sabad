"""
Live Flash Deal & Catalog Harvester for Sabad.
Executes concurrent network requests across SnappMarket, Digikala Jet, and Okala.
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional

from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.matcher import match_sku

logger = logging.getLogger(__name__)


class CatalogHarvester:
    """
    Concurrent harvester for multi-store catalog search and daily flash deals.
    """

    def __init__(self, adapters: Optional[Dict[str, BaseStoreAdapter]] = None):
        self.adapters = adapters or {
            "snapp_market": SnappMarketAdapter(),
            "digikala_jet": DigikalaJetAdapter(),
            "okala": OkalaAdapter(),
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

        # Step 3: Match results against parsed criteria
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]] = {
            item.raw_text: {} for item in basket_items
        }

        for (raw_text, s_name, item_obj), candidates_or_err in zip(
            search_keys, search_results
        ):
            if isinstance(candidates_or_err, Exception):
                logger.error(
                    f"Search error for '{raw_text}' on {s_name}: {candidates_or_err}"
                )
                catalog_matches[raw_text][s_name] = None
            else:
                candidates: List[StoreItem] = candidates_or_err
                best_match = match_sku(item_obj, candidates)
                catalog_matches[raw_text][s_name] = best_match

        return store_infos, catalog_matches
