"""
Post-LLM pillar routing and validation layer.

After the LLM returns v2.0 JSON, this module:
1. Validates that every finding/recommendation lives in the correct pillar bucket.
2. Re-routes misplaced items using the deterministic keyword table.
3. Distributes v1.1-style parameter extractions into pillar buckets.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from models.pillar_models import (
    PillarEnum,
    keyword_route,
    area_to_pillar,
    PARAM_AREA_TO_PILLAR,
    empty_pillar,
    PILLAR_ORDER,
)

logger = logging.getLogger(__name__)


def validate_and_fix_pillar_assignments(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every item's ``pillar`` field matches the key it sits under.

    If the LLM placed an item under the wrong pillar key, move it to the
    correct bucket (determined by the item's own ``pillar`` field).  If the
    item has no ``pillar`` field, infer one via keyword routing on its Area
    and Finding text and move it accordingly.

    Returns the (mutated) *data* dict.
    """
    pillars = data.get("Pillars")
    if not isinstance(pillars, dict):
        return data

    # Collect all items that need moving: list of (item, collection_key, correct_pillar)
    to_move: List[tuple[Dict, str, str]] = []

    for pillar_key in PILLAR_ORDER:
        bucket = pillars.get(pillar_key)
        if not isinstance(bucket, dict):
            continue

        for collection_key in ("findings", "positives", "recommendations"):
            items = bucket.get(collection_key)
            if not isinstance(items, list):
                continue

            keep = []
            for item in items:
                claimed_pillar = item.get("pillar", "")
                if not claimed_pillar:
                    # Infer from Area + Finding text
                    text = f"{item.get('Area', '')} {item.get('Finding', '')} {item.get('Description', '')}"
                    inferred = keyword_route(text) or PillarEnum.UNCATEGORIZED
                    item["pillar"] = inferred
                    claimed_pillar = inferred

                if claimed_pillar == pillar_key:
                    keep.append(item)
                else:
                    to_move.append((item, collection_key, claimed_pillar))
            bucket[collection_key] = keep

    # Place moved items into correct buckets
    for item, collection_key, target_pillar in to_move:
        if target_pillar not in pillars:
            pillars[target_pillar] = empty_pillar()
        target_bucket = pillars[target_pillar]
        if collection_key not in target_bucket:
            target_bucket[collection_key] = []
        target_bucket[collection_key].append(item)
        logger.info(
            "Moved %s '%s' → pillar '%s'",
            collection_key,
            item.get("Issue ID", item.get("Recommendation ID", "?")),
            target_pillar,
        )

    # Ensure all 8 pillar keys exist
    for pillar_key in PILLAR_ORDER:
        if pillar_key not in pillars:
            pillars[pillar_key] = empty_pillar()

    return data


def distribute_parameters(
    data: Dict[str, Any],
    parameters: List[Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """Attach extracted parameters to their matching pillar bucket.

    Each parameter gets a ``pillar`` field based on its ``area`` and is
    appended to ``Pillars.<pillar>.parameters``.  The original
    ``parameters`` list is *not* stored at the top level.
    """
    if not parameters:
        return data

    pillars = data.get("Pillars")
    if not isinstance(pillars, dict):
        return data

    for param in parameters:
        area = param.get("area", "")
        pillar_key = PARAM_AREA_TO_PILLAR.get(area.lower(), None)
        if pillar_key is None:
            pillar_key = keyword_route(area) or PillarEnum.UNCATEGORIZED
        param["pillar"] = pillar_key

        if pillar_key not in pillars:
            pillars[pillar_key] = empty_pillar()
        bucket = pillars[pillar_key]
        if "parameters" not in bucket:
            bucket["parameters"] = []
        bucket["parameters"].append(param)

    return data
