# PDF Metadata Extraction

This module provides functionality to extract System ID and Report Date from PDF files using AI-based extraction with fallback mechanisms.

## Features

1. **AI-Based Extraction**: Uses a lightweight LLM (gpt-4.1-mini by default) to extract metadata from the first page of PDF files
2. **Regex Fallback**: If AI extraction fails, falls back to regex pattern matching
3. **Filename Validation Fallback**: If both AI and regex fail, falls back to the original filename validation
4. **Multiple Date Format Support**: Normalizes various date formats to dd.mm.yyyy

## How It Works

1. The system first attempts to extract text from the first page of the uploaded PDF
2. It then tries to use AI to extract the System ID and Report Date from this text
3. If AI extraction fails, it falls back to regex pattern matching
4. If both methods fail, it falls back to the original filename validation (<SID>_ddmmyy.pdf)

## Configuration

The AI extraction uses the following environment variables:

- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION`: Azure OpenAI API version (defaults to "2024-12-01-preview")
- `AZURE_OPENAI_FAST_MODEL`: Fast model for extraction (defaults to "gpt-4.1-mini")

## Supported Date Formats

The system can normalize the following date formats to dd.mm.yyyy:

- dd.mm.yyyy
- dd/mm/yyyy
- dd-mm-yyyy
- yyyy.mm.dd
- ddmmyyyy

## API Integration

The functionality is integrated into the `/api/upload` endpoint in `storage_router.py`. No frontend changes are required.

## Error Handling

If all extraction methods fail, the system returns a helpful error message suggesting the filename format fallback.
