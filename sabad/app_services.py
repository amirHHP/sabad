"""Application services shared by the Streamlit and ASGI entry points.

The UI is responsible for widgets and presentation; this module owns the
network-to-optimizer pipeline so it can be tested or exposed through another
web host without importing Streamlit widgets.
"""

from typing import Dict, List, Optional, Tuple

from sabad.harvester import CatalogHarvester
from sabad.models.catalog import StoreInfo, StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import OptimizationResult
from sabad.optimizer.milp_solver import MILPBasketOptimizer


async def compare_and_optimize_basket(
    basket_items: List[ParsedGroceryItem],
    latitude: float,
    longitude: float,
    split_penalty_tomans: int = 25000,
    allow_multi_store: bool = True,
    harvester: Optional[CatalogHarvester] = None,
) -> Tuple[
    CatalogHarvester,
    Dict[str, StoreInfo],
    Dict[str, Dict[str, Optional[StoreItem]]],
    Dict[str, List[StoreItem]],
    OptimizationResult,
]:
    """Fetch all stores concurrently, then solve the delivered basket cost."""
    active_harvester = harvester or CatalogHarvester()
    store_infos, catalog_matches = await active_harvester.harvest_catalog_matches(
        basket_items, latitude, longitude
    )
    try:
        flash_deals = await active_harvester.harvest_flash_deals(latitude, longitude)
    except Exception:
        # A temporary flash-deal endpoint failure should never hide regular prices.
        flash_deals = {}

    optimizer = MILPBasketOptimizer(split_penalty_tomans=split_penalty_tomans)
    result = optimizer.optimize(
        basket_items=basket_items,
        catalog_matches=catalog_matches,
        store_infos=store_infos,
        allow_multi_store=allow_multi_store,
        flash_deals_by_store=flash_deals,
    )
    return active_harvester, store_infos, catalog_matches, flash_deals, result

