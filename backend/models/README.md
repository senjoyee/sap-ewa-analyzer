# Gemini Integration for EWA Analyzer

This directory contains the Google Gemini model integration for the EWA Analyzer.

## Overview

The EWA Analyzer now supports both Azure OpenAI and Google Gemini models, allowing you to choose the best model for your use case.

## Setup

### 1. Install Dependencies

The required `google-genai` dependency is already included in `pyproject.toml`. Install it with:

```bash
pip install google-genai
```

### 2. Get Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create a new API key
3. Set the environment variable:

```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# Linux/Mac
export GEMINI_API_KEY=your_api_key_here
```

### 3. Configure Model

To use Gemini models, set the `AZURE_OPENAI_SUMMARY_MODEL` environment variable to a Gemini model name:

```bash
# Use Gemini 2.5 Flash
set AZURE_OPENAI_SUMMARY_MODEL=gemini-2.5-flash

# Use Gemini Pro (if available)
set AZURE_OPENAI_SUMMARY_MODEL=gemini-pro
```

## Supported Models

- `gemini-2.5-flash` - Fast, cost-effective model
- `gemini-pro` - High-quality reasoning model
- Any model starting with `gemini-` will be detected automatically

## Usage

Once configured, the EWA Analyzer will automatically use Gemini models without any code changes:

```python
# This will automatically detect and use Gemini if configured
orchestrator = EWAWorkflowOrchestrator()
result = await orchestrator.execute_workflow("document.pdf")
```

## Architecture

### GeminiClient (`gemini_client.py`)
- Wrapper around Google's Gemini API
- Handles JSON formatting and schema validation
- Provides consistent interface with OpenAI client

### EWAAgent Integration
- Automatically detects model type from name
- Routes requests to appropriate API (OpenAI or Gemini)
- Maintains same interface for both model types

## Testing

Run the integration test to verify everything is working:

```bash
cd backend
python test_gemini_integration.py
```

## Troubleshooting

### Common Issues

1. **Missing API Key**
   ```
   ValueError: GEMINI_API_KEY environment variable is required
   ```
   Solution: Set the `GEMINI_API_KEY` environment variable

2. **Invalid Model Name**
   ```
   ValueError: Model 'invalid-model' is not a Gemini model
   ```
   Solution: Use a valid Gemini model name (starting with 'gemini-')

3. **JSON Parsing Errors**
   - Gemini responses are automatically cleaned and parsed
   - The system includes retry logic for malformed responses

### Debug Mode

To see detailed logs, the system prints model selection:
```
Creating EWAAgent with Gemini model: gemini-2.5-flash
```

## Performance Considerations

- **Gemini 2.5 Flash**: Faster response times, lower cost
- **Gemini Pro**: Higher quality analysis, slower response
- **Cost**: Gemini models may have different pricing than OpenAI

## Switching Back to OpenAI

To switch back to OpenAI models, simply change the environment variable:

```bash
set AZURE_OPENAI_SUMMARY_MODEL=gpt-4.1-mini
```

The system will automatically detect and use the OpenAI client.
