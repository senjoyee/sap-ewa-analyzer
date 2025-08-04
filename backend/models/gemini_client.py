"""
Google Gemini client wrapper for EWA Analyzer
"""

import os
import json
from typing import Dict, Any, Optional
from google import genai
from google.genai import types


class GeminiClient:
    """Wrapper class for Google Gemini API client"""
    
    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini client
        
        Args:
            api_key: Gemini API key (defaults to environment variable)
            model: Model name to use
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
            
        self.model = model
        self.client = genai.Client(api_key=self.api_key)
    
    def generate_content(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate content using Gemini API
        
        Args:
            prompt: User prompt/input text
            system_prompt: System prompt (will be prepended to user prompt)
            
        Returns:
            Generated content as string
        """
        try:
            # Combine system and user prompts
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Create content structure
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=full_prompt),
                    ],
                ),
            ]
            
            # Configure generation
            generate_content_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=-1,  # Unlimited thinking budget
                ),
            )
            
            # Generate content
            response_parts = []
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.text:
                    response_parts.append(chunk.text)
            
            return "".join(response_parts)
            
        except Exception as e:
            print(f"Error generating content with Gemini: {str(e)}")
            raise
    
    def generate_json_content(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        Generate JSON content using Gemini API
        
        Args:
            prompt: User prompt/input text
            system_prompt: System prompt (will be prepended to user prompt)
            
        Returns:
            Parsed JSON response as dictionary
        """
        try:
            # Add JSON formatting instruction to the prompt
            json_instruction = "\n\nIMPORTANT: Return your response as valid JSON only. Do not include any markdown formatting, explanations, or text outside the JSON structure."
            
            full_prompt = prompt + json_instruction
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{full_prompt}"
            
            response_text = self.generate_content(full_prompt)
            
            # Clean response and extract JSON
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]   # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove closing ```
            
            response_text = response_text.strip()
            
            # Parse JSON
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response from Gemini: {str(e)}")
            print(f"Raw response: {response_text}")
            raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")
        except Exception as e:
            print(f"Error generating JSON content with Gemini: {str(e)}")
            raise


def is_gemini_model(model_name: str) -> bool:
    """
    Check if the given model name is a Gemini model
    
    Args:
        model_name: Name of the model to check
        
    Returns:
        True if it's a Gemini model, False otherwise
    """
    return model_name.lower().startswith('gemini')


def create_gemini_client(model_name: str) -> GeminiClient:
    """
    Create a Gemini client for the specified model
    
    Args:
        model_name: Name of the Gemini model
        
    Returns:
        Configured GeminiClient instance
    """
    if not is_gemini_model(model_name):
        raise ValueError(f"Model '{model_name}' is not a Gemini model")
    
    return GeminiClient(model=model_name)
