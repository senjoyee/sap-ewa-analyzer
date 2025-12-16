"""On-demand batch status refresh and completion handling."""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Any, List, Optional

from batch.batch_registry import (
    list_pending,
    update_status,
    delete_entry,
)
from batch.openai_batch_client import get_batch, download_batch_output
from core.azure_clients import get_blob_client, AZURE_STORAGE_CONTAINER_NAME
from workflow_orchestrator import ewa_orchestrator


def _extract_summary_json(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the summary JSON from a batch output line."""
    resp = item.get("response") or {}
    outputs = resp.get("output") or []
    for out in outputs:
        for content in out.get("content", []):
            ctype = content.get("type")
            if ctype in ("output_parsed", "parsed"):
                parsed = content.get("parsed")
                if isinstance(parsed, dict):
                    return parsed
            if ctype in ("output_text", "text"):
                text = content.get("text")
                if isinstance(text, str):
                    try:
                        return json.loads(text)
                    except Exception:
                        # Best effort: ignore parse failure
                        return None
    return None


async def refresh_batches_on_demand() -> None:
    """Poll pending batches once (used when frontend refreshes)."""
    pending = list_pending()
    if not pending:
        return

    for entity in pending:
        blob_name = entity.get("RowKey")
        batch_id = entity.get("batch_id")
        if not blob_name or not batch_id:
            continue
        try:
            batch = await get_batch(batch_id)
            status = getattr(batch, "status", None) or getattr(batch, "state", None)
            if status in ("completed", "failed", "canceled"):
                await _handle_batch_done(blob_name, batch, status)
        except Exception as e:
            update_status(blob_name, "failed", error=str(e))


async def _handle_batch_done(blob_name: str, batch, status: str):
    """Handle completion or failure."""
    blob_client = get_blob_client(blob_name)
    # default to failed on unexpected issues
    new_status = "failed" if status != "completed" else "completed"
    try:
        meta = (await asyncio.to_thread(blob_client.get_blob_properties)).metadata or {}
        meta = meta.copy()
        meta["last_status"] = new_status
        meta["processing"] = "false"
        await asyncio.to_thread(blob_client.set_blob_metadata, meta)
    except Exception:
        pass

    if new_status != "completed":
        update_status(blob_name, "failed", error=f"batch status: {status}")
        return

    try:
        outputs = await download_batch_output(batch)
        saved = False
        for item in outputs:
            summary_json = _extract_summary_json(item)
            if summary_json:
                await ewa_orchestrator.save_results_step_from_json(blob_name, summary_json)
                saved = True
                break
        if saved:
            update_status(blob_name, "completed", error="")
            delete_entry(blob_name)
        else:
            update_status(blob_name, "failed", error="No parsable summary JSON in batch output")
    except Exception as e:
        update_status(blob_name, "failed", error=str(e))
