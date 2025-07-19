"""
Unified OpenAI Chat Completion Utility

This module provides a single async function to handle all OpenAI chat completions in the EWA Analyzer backend.
Supports:
- Model-specific parameterization (o-series, gpt-series, etc.)
- Function-calling (for schema-driven extraction)
- Token usage logging
- Robust exception handling
"""

import asyncio
import traceback

async def call_openai_chat(
    client,
    model: str,
    messages: list,
    *,
    functions=None,
    function_call=None,
    max_tokens=16384,
    temperature=0.0,
    reasoning_effort=None,
    **extra_params
):
    """
    Unified async OpenAI chat completion utility.
    Args:
        client: Azure OpenAI client
        model: Model name (e.g., 'gpt-4.1-mini', 'o4-mini')
        messages: List of message dicts (system/user/assistant)
        functions: Optional, list of function-calling definitions
        function_call: Optional, function-calling directive
        max_tokens: For GPT models, max tokens for completion (default 16384)
        max_completion_tokens: For reasoning models (e.g., o3, o4, o4-mini), sets completion token limit (default 32768)
        temperature: Sampling temperature (default 0.0)
        reasoning_effort: For reasoning models, set to 'high' for best reasoning
        extra_params: Any additional parameters for the API
    Returns:
        OpenAI API response object
    Raises:
        Exception if the API call fails
    """
    loop = asyncio.get_running_loop()
    def call():
        params = {
            "model": model,
            "messages": messages,
        }
        # Function-calling support
        if functions:
            params["functions"] = functions
        if function_call:
            params["function_call"] = function_call
        # Model-specific params
        if any(x in model for x in ["o3", "o4", "o4-mini"]):
            params["max_completion_tokens"] = 32768
            if reasoning_effort:
                params["reasoning_effort"] = reasoning_effort
        else:
            params["max_tokens"] = max_tokens
            params["temperature"] = temperature
        # Allow override/extension
        params.update(extra_params)
        return client.chat.completions.create(**params)
    try:
        response = await loop.run_in_executor(None, call)
        # Token usage logging
        if hasattr(response, 'usage') and response.usage is not None:
            prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
            completion_tokens = getattr(response.usage, 'completion_tokens', None)
            total_tokens = getattr(response.usage, 'total_tokens', None)
            print(f"[TOKEN USAGE] Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {total_tokens}")
        return response
    except Exception as e:
        print("[call_openai_chat] Exception occurred:")
        traceback.print_exc()
        raise
