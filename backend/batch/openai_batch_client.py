"""Azure OpenAI Batch helpers (submission and retrieval)."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI


AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_SUMMARY_MODEL = os.getenv("AZURE_OPENAI_SUMMARY_MODEL", "gpt-4.1")


def _client() -> AzureOpenAI:
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
        raise RuntimeError("Azure OpenAI credentials not configured (AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY).")
    return AzureOpenAI(
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
    )


def _jsonl_path(tasks: List[Dict[str, Any]]) -> str:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return path


async def submit_batch(tasks: List[Dict[str, Any]], completion_window: str = "24h") -> str:
    """Upload JSONL and create a batch job. Returns batch_id."""
    client = _client()
    path = _jsonl_path(tasks)
    try:
        with open(path, "rb") as fh:
            uploaded = await asyncio.to_thread(client.files.create, file=fh, purpose="batch")
        batch = await asyncio.to_thread(
            client.batches.create,
            input_file_id=uploaded.id,
            endpoint="/v1/responses",
            completion_window=completion_window,
            model=AZURE_OPENAI_SUMMARY_MODEL,
        )
        return batch.id
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


async def get_batch(batch_id: str):
    client = _client()
    return await asyncio.to_thread(client.batches.retrieve, batch_id)


async def download_batch_output(batch) -> List[Dict[str, Any]]:
    """Return parsed JSONL output if available."""
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        return []
    client = _client()
    file_bytes = await asyncio.to_thread(client.files.content, output_file_id)
    lines = file_bytes.text.splitlines()
    return [json.loads(line) for line in lines if line.strip()]
