"""Registry for tracking Azure OpenAI batch jobs in Azure Table Storage."""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from core.azure_clients import get_table_client, AZURE_BATCH_TABLE_NAME
from azure.data.tables import UpdateMode

PARTITION_KEY_DEFAULT = "default"


def _table():
    return get_table_client(AZURE_BATCH_TABLE_NAME)


def upsert_batch(blob_name: str, batch_id: str, status: str = "scheduled", error: str = "") -> None:
    entity = {
        "PartitionKey": PARTITION_KEY_DEFAULT,
        "RowKey": blob_name,
        "batch_id": batch_id,
        "status": status,
        "error": error or "",
        "updated_at": int(time.time()),
    }
    tbl = _table()
    tbl.upsert_entity(mode=UpdateMode.MERGE, entity=entity)


def update_status(blob_name: str, status: str, error: str = "") -> None:
    tbl = _table()
    entity = {
        "PartitionKey": PARTITION_KEY_DEFAULT,
        "RowKey": blob_name,
        "status": status,
        "error": error or "",
        "updated_at": int(time.time()),
    }
    tbl.upsert_entity(mode=UpdateMode.MERGE, entity=entity)


def list_pending() -> List[Dict]:
    tbl = _table()
    # pending are those not completed/failed
    query = "status ne 'completed' and status ne 'failed'"
    return list(tbl.query_entities(query))


def delete_entry(blob_name: str) -> None:
    tbl = _table()
    try:
        tbl.delete_entity(PARTITION_KEY_DEFAULT, blob_name)
    except Exception:
        pass


def get_entry(blob_name: str) -> Optional[Dict]:
    tbl = _table()
    try:
        return tbl.get_entity(PARTITION_KEY_DEFAULT, blob_name)
    except Exception:
        return None
