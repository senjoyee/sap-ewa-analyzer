"""Chat endpoint extracted from ewa_main.py.

This is functionally identical to the previous implementation, just wrapped in an APIRouter so
that main stays slim.  No behavioural changes.
"""

from __future__ import annotations

import os
import traceback
from typing import List, Dict, Any

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
        model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
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

        messages = [{"role": "system", "content": system_prompt}]
        recent_history = request.chatHistory[-10:] if len(request.chatHistory) > 10 else request.chatHistory
        for msg in recent_history:
            role = "user" if msg.get("isUser") else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})
        messages.append({"role": "user", "content": request.message})

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=2000,
                temperature=0.2,
                top_p=0.95,
            )
            ai_response = response.choices[0].message.content
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


def _build_system_prompt(filename: str, doc_content: str) -> str:
    """Return the same long system prompt used previously (condensed slightly)."""
    return f"""You are an expert SAP Basis Architect specialized in analyzing SAP Early Watch Alert (EWA) reports.\n\nDOCUMENT: {filename}\nCONTENT:\n{doc_content}\n\nIMPORTANT INSTRUCTIONS:\n1. This is an SAP Early Watch Alert (EWA) report which contains system performance metrics, issues, warnings, and recommendations.\n2. The report typically covers areas like database statistics, memory usage, backup frequency, system availability, and performance parameters.\n3. When answering questions, focus on extracting SPECIFIC INFORMATION from the document, even if it's just a brief mention.\n4. If information is present but brief, explain it and note that limited details are available.\n5. Be especially attentive to technical metrics, parameter recommendations, and critical warnings in the report.\n6. Quote specific sections and values from the report whenever possible.\n7. If you truly cannot find ANY mention of a topic, only then state that it's not in the document.\n\nDIRECTING USERS TO SPECIALIZED SECTIONS:\n1. This application has DEDICATED SECTIONS for Key Metrics and Parameters that provide more detailed and structured information.\n2. When users ask about specific metrics, give a brief summary (exclude numeric values) and direct them explicitly to the Key Metrics section.\n3. When users ask about parameters, give a brief summary (exclude numeric values) and direct them explicitly to the Parameters section.\n\nProvide technically precise answers in Markdown."""


def _humanize_openai_error(err: Exception, model_name: str) -> str:
    txt = str(err).lower()
    if "not found" in txt and "model" in txt:
        return f"Model '{model_name}' not found. Please check configuration."
    if "authenticate" in txt or "key" in txt:
        return "Authentication error. Please check Azure OpenAI API key and endpoint."
    if "rate limit" in txt:
        return "Rate limit exceeded. Please try again later."
    return str(err)
