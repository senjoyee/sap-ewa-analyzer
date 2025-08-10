import os
import sys
import json
import asyncio
import traceback
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Allow importing from backend package root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, BACKEND_ROOT)

from openai import AzureOpenAI  # type: ignore
from agent.ewa_agent import EWAAgent  # type: ignore


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None else default


async def main():
    if load_dotenv:
        load_dotenv()

    azure_endpoint = get_env("AZURE_OPENAI_ENDPOINT")
    api_key = get_env("AZURE_OPENAI_API_KEY")
    api_version = get_env("AZURE_OPENAI_API_VERSION", "preview")
    model = get_env("AZURE_OPENAI_SUMMARY_MODEL")

    if not azure_endpoint or not api_key or not model:
        print("Missing required environment variables. Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION (preview or later), and AZURE_OPENAI_SUMMARY_MODEL.")
        sys.exit(1)

    print(f"Using model: {model} | API version: {api_version}")

    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    # Minimal markdown content for smoke test
    markdown = (
        "# SAP EarlyWatch Alert (EWA)\n\n"
        "System: ABC (SID)\n\n"
        "Report Date: 01.01.2025\n\n"
        "## Performance Indicators\n\n"
        "Average dialog response time: 528ms\n"
    )

    # Optional PDF path argument to exercise PDF input path
    pdf_data = None
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        try:
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            print(f"Loaded PDF bytes from: {pdf_path} ({len(pdf_data)} bytes)")
        except Exception as e:
            print(f"Warning: Could not read PDF at {pdf_path}: {e}. Continuing with markdown-only.")
            pdf_data = None

    agent = EWAAgent(client=client, model=model)

    try:
        result = await agent.run(markdown, pdf_data=pdf_data)
        print("=== Responses API Smoke Test Output (truncated) ===")
        print(json.dumps(result, indent=2)[:5000])
        print("=== End Output ===")
    except Exception:
        print("Smoke test failed with exception:")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
