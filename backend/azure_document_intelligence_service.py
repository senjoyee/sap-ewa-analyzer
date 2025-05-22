import os
import json
import re
import unicodedata
import time
from datetime import datetime
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.exceptions import HttpResponseError
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
AZURE_DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

if not AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or not AZURE_DOCUMENT_INTELLIGENCE_KEY:
    raise ValueError(
        "Azure Document Intelligence endpoint and key must be set in .env file "
        "(AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT, AZURE_DOCUMENT_INTELLIGENCE_KEY)"
    )

if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
    raise ValueError(
        "Azure Storage connection string and container name must be set in .env file "
        "(AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER_NAME)"
    )

document_intelligence_client = DocumentIntelligenceClient(
    endpoint=AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT, credential=AzureKeyCredential(AZURE_DOCUMENT_INTELLIGENCE_KEY)
)

# Initialize BlobServiceClient
try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
except Exception as e:
    print(f"Error initializing BlobServiceClient: {e}")
    blob_service_client = None

# Dictionary to track the status of document analysis jobs
# Structure: {blob_name: {"status": "pending|processing|completed|failed", "start_time": timestamp, "end_time": timestamp, "message": "message", "result": result_dict}}
analysis_status_tracker = {}

def analyze_document_layout(file_bytes: bytes, content_type: str = "application/octet-stream"):
    """
    Analyzes the layout of a document provided as bytes.

    Args:
        file_bytes: The bytes of the file to analyze.
        content_type: The content type of the file (e.g., 'application/pdf', 'image/jpeg').
                      Defaults to 'application/octet-stream' for general binary data.

    Returns:
        A dictionary containing the extracted layout information (pages, lines, tables),
        or an error dictionary if analysis fails.
    """
    try:
        poller = document_intelligence_client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=file_bytes,
            content_type=content_type
        )
        result = poller.result()

        # The result object from the SDK is already dictionary-like and serializable to JSON.
        # We can directly use to_dict() if available, or construct our simplified one if needed.
        # For prebuilt-layout, the structure is fairly standard.
        # The custom dictionary construction below ensures we capture what we need.

        extracted_data = {
            "model_id": result.model_id,
            "api_version": result.api_version,
            "content_format": result.content_format,
            "content": result.content, # Full text content
            "pages": [],
            "paragraphs": [],
            "tables": [],
            "styles": [] # Include styles if present and useful
        }

        if result.pages:
            for page_idx, page in enumerate(result.pages):
                page_data = {
                    "page_number": page.page_number,
                    "angle": page.angle,
                    "width": page.width,
                    "height": page.height,
                    "unit": page.unit,
                    "spans": [(span.offset, span.length) for span in page.spans or []],
                    "words": [
                        {
                            "content": word.content,
                            "polygon": word.polygon,
                            "confidence": word.confidence,
                            "span": (word.span.offset, word.span.length)
                        } for word in page.words or []
                    ],
                    "lines": [
                        {
                            "content": line.content,
                            "polygon": line.polygon,
                            "spans": [(span.offset, span.length) for span in line.spans or []]
                        } for line in page.lines or []
                    ],
                    "selection_marks": [
                        {
                            "state": mark.state,
                            "polygon": mark.polygon,
                            "confidence": mark.confidence,
                            "span": (mark.span.offset, mark.span.length)
                        } for mark in page.selection_marks or []
                    ]
                }
                extracted_data["pages"].append(page_data)
        
        if result.paragraphs:
            for paragraph in result.paragraphs:
                extracted_data["paragraphs"].append({
                    "role": paragraph.role,
                    "content": paragraph.content,
                    "bounding_regions": [
                        {
                            "page_number": region.page_number,
                            "polygon": region.polygon
                        } for region in paragraph.bounding_regions or []
                    ],
                    "spans": [(span.offset, span.length) for span in paragraph.spans or []]
                })

        if result.tables:
            for table_idx, table in enumerate(result.tables):
                table_data = {
                    "table_number": table_idx + 1,
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "bounding_regions": [
                        {
                            "page_number": region.page_number,
                            "polygon": region.polygon
                        } for region in table.bounding_regions or []
                    ],
                    "spans": [(span.offset, span.length) for span in table.spans or []],
                    "cells": []
                }
                for cell in table.cells:
                    table_data["cells"].append({
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "row_span": cell.row_span if cell.row_span else 1,
                        "column_span": cell.column_span if cell.column_span else 1,
                        "content": cell.content,
                        "kind": cell.kind,
                        "bounding_regions": [
                            {
                                "page_number": region.page_number,
                                "polygon": region.polygon
                            } for region in cell.bounding_regions or []
                        ],
                        "spans": [(span.offset, span.length) for span in cell.spans or []]
                    })
                extracted_data["tables"].append(table_data)
        
        if result.styles:
            for style in result.styles:
                extracted_data["styles"].append({
                    "is_handwritten": getattr(style, 'is_handwritten', None),
                    "spans": [(span.offset, span.length) for span in style.spans or []],
                    "confidence": getattr(style, 'confidence', None),
                    "font_size": getattr(style, 'font_size', None),
                    "font_weight": getattr(style, 'font_weight', None),
                    "color": getattr(style, 'color', None),
                    "background_color": getattr(style, 'background_color', None)
                })
        return extracted_data

    except HttpResponseError as e:
        return {"error": True, "message": f"Azure Document Intelligence API error: {e.message}", "status_code": e.status_code, "details": str(e)}
    except Exception as e:
        return {"error": True, "message": f"An unexpected error occurred: {str(e)}"}

def preprocess_analysis_for_llm(analysis_data: dict) -> dict:
    """
    Preprocesses the full analysis result to create a slimmer version
    focused on textual content and table structure for LLM consumption.
    """
    if analysis_data.get("error"):
        return analysis_data

    # Extract flat paragraphs and tables
    paras = extract_paragraphs(analysis_data)
    tbls = extract_tables(analysis_data)

    # Group paragraphs by page and join
    page_texts = {}
    for p in paras:
        pg = p.get("page")
        txt = clean(p.get("text", ""))
        if pg is None or not txt:
            continue
        page_texts.setdefault(pg, []).append(txt)
    paragraphs = [
        {"page": pg, "text": "\n".join(lines)}
        for pg, lines in sorted(page_texts.items())
    ]

    # Process tables compactly
    tables = []
    for t in tbls:
        pg = t.get("page")
        if pg is None:
            continue
        cells = [[clean(cell) for cell in row] for row in t.get("cells", [])]
        tables.append({"page": pg, "cells": cells})

    return {"paragraphs": paragraphs, "tables": tables}

# --- User-provided helper functions for compact output --- 
def extract_paragraphs(di: dict) -> list[dict]:
    body      = di.get("content", "") # Default to empty string if no content
    out       = []
    paragraphs = di.get("paragraphs", [])

    for p in paragraphs:
        # Each paragraph can have 1-N spans → concatenate
        text = "".join(
            body[s[0] : s[0] + s[1]] # Corrected: s is a tuple (offset, length)
            for s in p.get("spans", [])
        )
        page_number = None
        if p.get("bounding_regions") and p["bounding_regions"]:
             page_number = p["bounding_regions"][0].get("page_number")

        out.append({"page": page_number, "text": text.strip()})
    return out

def extract_tables(di: dict) -> list[dict]:
    body   = di.get("content", "") # Default to empty string if no content
    out    = []

    for t_idx, table in enumerate(di.get("tables", [])):
        # Ensure columnCount and rowCount are present and valid
        col_count = table.get("column_count", 0)
        row_count = table.get("row_count", 0)
        if col_count == 0 or row_count == 0:
            continue # Skip malformed tables
            
        rows = [[""] * col_count for _ in range(row_count)]

        for cell in table.get("cells", []) :
            txt = "".join(
                body[s[0]: s[0] + s[1]] # Corrected: s is a tuple (offset, length)
                for s in cell.get("spans", [])
            ).strip()
            # Ensure rowIndex and columnIndex are within bounds
            r_idx = cell.get("row_index", -1)
            c_idx = cell.get("column_index", -1)
            if 0 <= r_idx < row_count and 0 <= c_idx < col_count:
                 rows[r_idx][c_idx] = txt

        page_number = None
        if table.get("bounding_regions") and table["bounding_regions"]:
            page_number = table["bounding_regions"][0].get("page_number")

        out.append({"page": page_number, "cells": rows})
    return out

# chars you almost never want
_ZWSP = "[\u00ad\u200b\u200e\u200f]"

def clean(text: str) -> str:
    if not isinstance(text, str):
        return "" # Return empty string if text is not a string (e.g. None)
    text = unicodedata.normalize("NFKC", text)   # unicode squashing
    text = re.sub(_ZWSP, "", text)               # zero-width stuff
    text = re.sub(r"\s+", " ", text)             # collapse whitespace
    text = re.sub(r"•", "-", text)               # unify bullets
    # text = re.sub(r"Page \d+ of \d+", "", text)  # kill footers (example) - commented out as it might be too aggressive
    return text.strip()
# --- End of user-provided helper functions ---


def analyze_document_from_blob(blob_name: str) -> dict:
    """
    Analyzes a document stored in Azure Blob Storage and saves the analysis result 
    to the same container with a .json extension.
    
    Args:
        blob_name: The name of the blob to analyze.
        
    Returns:
        A dictionary containing information about the analysis process, including status and result location.
    """
    # Initialize status tracking for this job
    current_time = datetime.now().isoformat()
    analysis_status_tracker[blob_name] = {
        "status": "pending",
        "start_time": current_time,
        "message": "Analysis pending",
        "progress": 0
    }
    
    if not blob_service_client:
        analysis_status_tracker[blob_name] = {
            "status": "failed", 
            "end_time": datetime.now().isoformat(),
            "message": "Azure Blob Service client not initialized",
            "progress": 0
        }
        return {"error": True, "message": "Azure Blob Service client not initialized"}
    
    try:
        # Update status to processing
        analysis_status_tracker[blob_name].update({
            "status": "processing",
            "message": "Downloading document from storage",
            "progress": 10
        })
        
        # Get the blob client to download the file
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        blob_client = container_client.get_blob_client(blob_name)
        
        # Get file properties to determine content type
        properties = blob_client.get_blob_properties()
        content_type = properties.content_settings.content_type or "application/octet-stream"
        
        # Download the blob content
        print(f"Downloading {blob_name} from Azure Blob Storage...")
        blob_data = blob_client.download_blob().readall()
        
        # Update status
        analysis_status_tracker[blob_name].update({
            "message": "Document downloaded, starting analysis",
            "progress": 25
        })
        
        # Analyze the document
        print(f"Analyzing {blob_name} with content type: {content_type}...")
        analysis_status_tracker[blob_name].update({
            "message": "Document intelligence analysis in progress",
            "progress": 40
        })
        
        analysis_result = analyze_document_layout(blob_data, content_type=content_type)
        
        if analysis_result.get("error"):
            error_message = f"Error analyzing document: {analysis_result.get('message')}"
            analysis_status_tracker[blob_name].update({
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "message": error_message,
                "progress": 0
            })
            return {
                "error": True, 
                "message": error_message,
                "details": analysis_result.get('details', '')
            }
        
        # Update status    
        analysis_status_tracker[blob_name].update({
            "message": "Analysis complete, processing results",
            "progress": 70
        })
            
        # Process the result to create a cleaner output
        # We'll use the preprocess_analysis_for_llm function to create a slimmer version
        processed_result = preprocess_analysis_for_llm(analysis_result)
        
        # Generate output file name with .json extension
        base_name = os.path.splitext(blob_name)[0]
        output_blob_name = f"{base_name}.json"
        
        # Update status
        analysis_status_tracker[blob_name].update({
            "message": "Saving results to storage",
            "progress": 85
        })
        
        # Save the result back to blob storage
        output_blob_client = container_client.get_blob_client(output_blob_name)
        
        # Convert the result to JSON string
        result_json = json.dumps(processed_result, ensure_ascii=False, separators=(',',':'))
        
        # Upload the result back to blob storage
        print(f"Uploading analysis result to {output_blob_name}...")
        content_settings = ContentSettings(content_type="application/json")
        output_blob_client.upload_blob(result_json, overwrite=True, content_settings=content_settings)
        
        # Copy metadata from original blob to ensure we maintain customer information
        if properties.metadata:
            output_blob_client.set_blob_metadata(metadata=properties.metadata)
        
        # Final result
        result = {
            "success": True,
            "message": "Document analyzed successfully",
            "original_document": blob_name,
            "result_document": output_blob_name,
            "page_count": len(analysis_result.get('pages', [])),
            "paragraph_count": len(processed_result.get('paragraphs', [])),
            "table_count": len(processed_result.get('tables', []))
        }
        
        # Update status to completed
        analysis_status_tracker[blob_name].update({
            "status": "completed",
            "end_time": datetime.now().isoformat(),
            "message": "Analysis completed successfully",
            "progress": 100,
            "result": result
        })
        
        return result
        
    except Exception as e:
        import traceback
        error_message = f"An error occurred during blob analysis: {str(e)}"
        
        # Update status to failed
        analysis_status_tracker[blob_name].update({
            "status": "failed",
            "end_time": datetime.now().isoformat(),
            "message": error_message,
            "progress": 0
        })
        
        return {
            "error": True,
            "message": error_message,
            "traceback": traceback.format_exc()
        }

def get_analysis_status(blob_name: str) -> dict:
    """
    Gets the current status of a document analysis job.
    
    Args:
        blob_name: The name of the blob being analyzed.
        
    Returns:
        A dictionary containing the current status information.
    """
    if blob_name not in analysis_status_tracker:
        return {
            "error": True,
            "message": f"No analysis job found for {blob_name}"
        }
    
    # Return a copy of the status to avoid modification issues
    status = dict(analysis_status_tracker[blob_name])
    
    # Add estimated time remaining if job is still processing
    if status.get("status") == "processing":
        # Calculate elapsed time
        start_time = datetime.fromisoformat(status.get("start_time"))
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        
        # Calculate estimated time remaining based on progress
        progress = status.get("progress", 0)
        if progress > 0:
            # Simple estimation: if X% took Y seconds, 100% will take (Y/X)*100 seconds
            estimated_total_seconds = (elapsed_seconds / progress) * 100
            remaining_seconds = estimated_total_seconds - elapsed_seconds
            
            # Add to status
            status["elapsed_seconds"] = int(elapsed_seconds)
            status["estimated_remaining_seconds"] = max(0, int(remaining_seconds))
    
    return status

# Example usage (for testing this module directly):
if __name__ == "__main__":
    try:
        test_file_path = r"C:\Users\joyee.sen\Downloads\S4P_ABAP_05_05_2025.pdf" # <--- !!! ENSURE THIS PATH IS CORRECT !!!
        if os.path.exists(test_file_path):
            with open(test_file_path, "rb") as f:
                file_bytes_content = f.read()
            
            file_ext = os.path.splitext(test_file_path)[1].lower()
            ct = "application/octet-stream" # Default
            if file_ext == ".pdf":
                ct = "application/pdf"
            elif file_ext in [".jpg", ".jpeg"]:
                ct = "image/jpeg"
            elif file_ext == ".png":
                ct = "image/png"
            elif file_ext == ".tiff" or file_ext == ".tif":
                ct = "image/tiff"
            else:
                print(f"Unsupported file type for simple test: {file_ext}. Defaulting to octet-stream.")

            print(f"Analyzing file: {test_file_path} with content type: {ct}")
            analysis_result_data = analyze_document_layout(file_bytes_content, content_type=ct)

            if analysis_result_data.get("error"):
                print(f"Error analyzing document: {analysis_result_data.get('message')}")
                if analysis_result_data.get('details'):
                    print(f"Details: {analysis_result_data.get('details')}")
            else:
                print("Analysis successful!")

                # --- Build and write compact JSON with separate paragraphs and tables ---
                extracted_paragraphs = extract_paragraphs(analysis_result_data)
                extracted_tables = extract_tables(analysis_result_data)

                cleaned_paragraphs = [
                    {"page": p["page"], "text": clean(p["text"]) }
                    for p in extracted_paragraphs
                    if p.get("page") is not None and clean(p["text"])
                ]

                cleaned_tables = []
                for tbl in extracted_tables:
                    if tbl.get("page") is None:
                        continue
                    cleaned_cells = [[clean(cell) for cell in row] for row in tbl["cells"]]
                    cleaned_tables.append({"page": tbl["page"], "cells": cleaned_cells})

                output_data = {
                    "paragraphs": cleaned_paragraphs,
                    "tables": cleaned_tables
                }

                output_dir = os.path.dirname(test_file_path)
                base_filename = os.path.splitext(os.path.basename(test_file_path))[0]
                output_json_filename = os.path.join(output_dir, base_filename + ".json")
                
                with open(output_json_filename, "w", encoding="utf-8") as json_file:
                    json.dump(output_data, json_file, ensure_ascii=False, separators=(',',':'))
                print(f"Compact JSON output written to: {output_json_filename}")
                print(f"Paragraphs: {len(cleaned_paragraphs)}, Tables: {len(cleaned_tables)}")

                # Print some basic info from the original analysis if needed
                original_page_count = len(analysis_result_data.get('pages', []))
                if original_page_count > 0:
                    print(f"Original document processed {original_page_count} pages.")
                # Add more summary prints from analysis_result_data if desired

        else:
            print(f"Test file not found: {test_file_path}. Please update the path in the example usage.")

    except ImportError as ie:
        print(f"Missing an import for testing. Error: {ie}")
    except Exception as e:
        print(f"An error occurred during the test: {e}")
