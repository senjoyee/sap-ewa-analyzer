"""Chat endpoint extracted from ewa_main.py.

This is functionally identical to the previous implementation, just wrapped in an APIRouter so
that main stays slim.  No behavioural changes.
"""

from __future__ import annotations

import os
import traceback
from typing import List, Dict, Any
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Lazy import AzureOpenAI only when needed to avoid cost at module load

router = APIRouter(prefix="/api", tags=["chat"])


class ChatHistoryItem(BaseModel):
    text: str
    isUser: bool = True


class ChatRequest(BaseModel):
    message: str
    fileName: str
    documentContent: str
    fileOrigin: str = ""
    contentLength: int = 0
    chatHistory: List[Dict[str, Any]] = []


@router.post("/chat")
async def chat_with_document(request: ChatRequest):
    """Chat with a processed EWA Markdown document using Azure OpenAI GPT models."""
    # DEBUG: Log incoming request summary
    print("----- /api/chat CALL -----")
    try:
        print(f"file={request.fileName}, message_len={len(request.message)}, content_len={len(request.documentContent)}, history_len={len(request.chatHistory)}")
    except Exception as _logerr:
        print("Logging error:", _logerr)
    try:
        load_dotenv()
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        # Prefer summary/fast model names used elsewhere in the backend; fall back to legacy var
        model_name = (
            os.getenv("AZURE_OPENAI_SUMMARY_MODEL")
            or os.getenv("AZURE_OPENAI_FAST_MODEL")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
        )
        print(f"Azure endpoint set: {bool(azure_endpoint)}, model: {model_name}")

        if not api_key or not azure_endpoint:
            raise HTTPException(status_code=500, detail="Azure OpenAI environment variables missing.")

        from openai import AzureOpenAI  # local import to keep module import light

        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint,
        )

        doc_content = request.documentContent or ""
        if len(doc_content) < 50:
            doc_content = "No document content provided or content too short. Please process the document first."

        system_prompt = _build_system_prompt(request.fileName, doc_content)

        # Build Responses API input messages with content parts
        responses_messages = []
        responses_messages.append({
            "role": "system",
            "content": [{"type": "input_text", "text": system_prompt}],
        })
        recent_history = request.chatHistory[-10:] if len(request.chatHistory) > 10 else request.chatHistory
        for msg in recent_history:
            role = "user" if msg.get("isUser") else "assistant"
            text = msg.get("text", "")
            content_type = "input_text" if role == "user" else "output_text"
            responses_messages.append({
                "role": role,
                "content": [{"type": content_type, "text": text}],
            })
        responses_messages.append({
            "role": "user",
            "content": [{"type": "input_text", "text": request.message}],
        })

        try:
            # Use Azure OpenAI Responses API (GPT-5 compatible) off the event loop
            response = await asyncio.to_thread(
                lambda: client.responses.create(
                    model=model_name,
                    input=responses_messages,
                    max_output_tokens=4096,
                    reasoning={"effort": "medium"},
                    text={"verbosity": "concise"},
                )
            )
            # Log token usage if available
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    in_tok = getattr(usage, "input_tokens", None) if hasattr(usage, "input_tokens") else (usage.get("input_tokens") if isinstance(usage, dict) else None)
                    out_tok = getattr(usage, "output_tokens", None) if hasattr(usage, "output_tokens") else (usage.get("output_tokens") if isinstance(usage, dict) else None)
                    print(f"[Chat] Token usage: input_tokens={in_tok}, output_tokens={out_tok}")
            except Exception:
                pass

            ai_response = getattr(response, "output_text", None)
            if not ai_response:
                # Fallback: try to stringify response for debugging context
                try:
                    ai_response = response.model_dump_json() if hasattr(response, "model_dump_json") else str(response)
                except Exception:
                    ai_response = ""
            return {"response": ai_response}
        except Exception as api_err:
            print("OpenAI API error:", api_err)
            print(traceback.format_exc())
            err_text = _humanize_openai_error(api_err, model_name)
            return {"response": f"Error: {err_text}", "error": True}

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print("Chat endpoint error", tb)
        raise HTTPException(status_code=500, detail="Unexpected server error in chat endpoint.")


# Path to system prompt template
_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "chat_system_prompt.md")


def _build_system_prompt(filename: str, doc_content: str) -> str:
    """Return the chat system prompt, loading from markdown template if present."""
    if os.path.exists(_PROMPT_PATH):
        with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
            template = _f.read()
        return template.format(filename=filename, doc_content=doc_content)

    # Fallback inline prompt (legacy)
    return (
        "You are an expert SAP Basis Architect specialized in analyzing SAP Early Watch Alert (EWA) reports.\n\n"
        f"DOCUMENT: {filename}\nCONTENT:\n{doc_content}\n\n"
        "IMPORTANT INSTRUCTIONS:\n1. This is an SAP Early Watch Alert (EWA) report which contains system performance metrics, issues, warnings, and recommendations.\n"
        "2. The report typically covers areas like database statistics, memory usage, backup frequency, system availability, and performance parameters.\n"
        "3. When answering questions, focus on extracting SPECIFIC INFORMATION from the document, even if it's just a brief mention.\n"
        "4. If information is present but brief, explain it and note that limited details are available.\n"
        "5. Be especially attentive to technical metrics, parameter recommendations, and critical warnings in the report.\n"
        "6. Quote specific sections and values from the report whenever possible.\n"
        "7. If you truly cannot find ANY mention of a topic, only then state that it's not in the document.\n\n"
        "DIRECTING USERS TO SPECIALIZED SECTIONS:\n1. This application has DEDICATED SECTIONS for Key Metrics and Parameters that provide more detailed and structured information.\n"
        "2. When users ask about specific metrics, give a brief summary (exclude numeric values) and direct them explicitly to the Key Metrics section.\n"
        "3. When users ask about parameters, give a brief summary (exclude numeric values) and direct them explicitly to the Parameters section.\n\n"
        "Provide technically precise answers in Markdown."
    )


def _humanize_openai_error(err: Exception, model_name: str) -> str:
    txt = str(err).lower()
    if "not found" in txt and "model" in txt:
        return f"Model '{model_name}' not found. Please check configuration."
    if "deploymentnotfound" in txt or "deployment not found" in txt:
        return f"Deployment '{model_name}' not found. Verify Azure deployment name and AZURE_OPENAI_* environment variables."
    if "authenticate" in txt or "key" in txt:
        return "Authentication error. Please check Azure OpenAI API key and endpoint."
    if "rate limit" in txt:
        return "Rate limit exceeded. Please try again later."
    return str(err)
