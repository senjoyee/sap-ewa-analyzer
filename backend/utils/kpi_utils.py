"""Utility functions for KPI canonicalization and trend tracking."""

import os
import json
from typing import Dict, List, Tuple, Optional
from azure.storage.blob import BlobServiceClient
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")


def extract_customer_system_from_blob_name(blob_name: str, blob_service_client=None) -> Tuple[str, str]:
    """Extract customer and system identifiers from blob metadata.
    
    If metadata is not available, falls back to filename parsing.
    """
    # Try to get customer and system from blob metadata
    if blob_service_client:
        try:
            container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
            blob_client = blob_service_client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            blob_properties = blob_client.get_blob_properties()
            metadata = blob_properties.metadata or {}
            
            customer = metadata.get('customer')
            system = metadata.get('system_id') or metadata.get('system')
            
            if customer and system:
                return customer, system
        except Exception as e:
            print(f"Could not retrieve metadata for {blob_name}: {e}")
    
    # Fallback to filename parsing if metadata not available
    # Remove file extension
    base_name = os.path.splitext(blob_name)[0]
    
    # Split by underscores
    parts = base_name.split('_')
    
    # Handle cases where there might be underscores in customer or system names
    # Assume first part is customer, second part is system
    if len(parts) >= 3:
        customer = parts[0]
        system = parts[1]
        return customer, system
    
    # Fallback if format doesn't match expectations
    raise ValueError(f"Could not extract customer and system from blob name: {blob_name}")


def get_canonical_kpi_blob_name(customer: str, system: str) -> str:
    """Generate the blob name for the canonical KPI list."""
    return f"canonical_kpis/{customer}_{system}_canonical_kpis.json"


def get_previous_analysis_blob_name(customer: str, system: str, current_blob_name: str) -> str:
    """Generate the blob name for the previous analysis JSON."""
    # Remove file extension
    base_name = os.path.splitext(current_blob_name)[0]
    return f"{base_name}_AI.json"


def get_previous_kpi_data(customer: str, system: str, current_blob_name: str, blob_service_client=None) -> Tuple[List[Dict], List[str]]:
    """Get previous KPI data and canonical KPI names for trend analysis."""
    # Get canonical KPI names
    canonical_kpis = get_canonical_kpis(customer, system)
    canonical_kpi_names = [kpi['name'] for kpi in canonical_kpis]
    
    # Get previous KPI data
    previous_kpis = []
    
    try:
        # Use provided blob service client or create a new one
        if blob_service_client is None:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
        
        # List all blobs with customer_system prefix
        prefix = f"{customer}_{system}_"
        blobs = list(container_client.list_blobs(name_starts_with=prefix))
        
        # Filter for JSON files and get their metadata
        json_blobs_with_metadata = []
        for blob in blobs:
            if blob.name.endswith('_AI.json') and blob.name != current_blob_name.replace('.md', '_AI.json'):
                # Get blob metadata to extract report date
                blob_client = container_client.get_blob_client(blob.name)
                blob_properties = blob_client.get_blob_properties()
                metadata = blob_properties.metadata or {}
                report_date = metadata.get('report_date')
                
                # Only include blobs with report_date metadata
                if report_date:
                    json_blobs_with_metadata.append({
                        'blob': blob,
                        'report_date': report_date
                    })
        
        # Sort by report date (newest first)
        json_blobs_with_metadata.sort(key=lambda x: x['report_date'], reverse=True)
        
        # Get the most recent one that's not the current blob
        if json_blobs_with_metadata:
            blob = json_blobs_with_metadata[0]['blob']
            # Download and parse the JSON
            blob_client = container_client.get_blob_client(blob.name)
            data = json.loads(blob_client.download_blob().readall().decode('utf-8'))
            previous_kpis = data.get('kpis', [])
    except Exception as e:
        print(f"Could not retrieve previous KPI data: {e}")
    
    return previous_kpis, canonical_kpi_names


def save_canonical_kpis(customer: str, system: str, kpis: List[Dict]) -> bool:
    """Save the canonical KPI list for a customer/system combination."""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        
        canonical_blob_name = get_canonical_kpi_blob_name(customer, system)
        canonical_blob_client = blob_service_client.get_blob_client(
            container=AZURE_STORAGE_CONTAINER_NAME, 
            blob=canonical_blob_name
        )
        
        # Save canonical KPIs
        canonical_blob_client.upload_blob(
            json.dumps(kpis, indent=2).encode('utf-8'), 
            overwrite=True,
            content_type="application/json"
        )
        
        print(f"Saved canonical KPI list to {canonical_blob_name}")
        return True
        
    except Exception as e:
        print(f"Error saving canonical KPI list: {e}")
        return False


def update_kpi_trends(current_kpis: List[Dict], previous_kpis: List[Dict]) -> List[Dict]:
    """Update KPI objects with trend information based on previous values."""
    # Create a lookup dictionary for previous KPIs by name
    previous_kpi_lookup = {kpi['name']: kpi for kpi in previous_kpis}
    
    updated_kpis = []
    for kpi in current_kpis:
        kpi_name = kpi['name']
        updated_kpi = kpi.copy()
        
        # Initialize trend as flat if no previous data
        updated_kpi['trend'] = {'direction': 'flat'}
        
        # If we have previous data for this KPI, calculate trend
        if kpi_name in previous_kpi_lookup:
            previous_kpi = previous_kpi_lookup[kpi_name]
            try:
                # Extract numeric values from current and previous KPIs
                current_value_str = kpi['current_value']
                previous_value_str = previous_kpi['current_value']
                
                # Simple numeric extraction (this could be enhanced for complex units)
                # Handle cases where the value might have units like "ms", "%", "GB", etc.
                current_num_str = ''.join(filter(lambda x: x.isdigit() or x == '.', current_value_str))
                previous_num_str = ''.join(filter(lambda x: x.isdigit() or x == '.', previous_value_str))
                
                if current_num_str and previous_num_str:
                    current_num = float(current_num_str)
                    previous_num = float(previous_num_str)
                    
                    if previous_num != 0:
                        percent_change = ((current_num - previous_num) / previous_num) * 100
                        updated_kpi['trend']['percent_change'] = round(percent_change, 2)
                        
                        if percent_change > 0:
                            updated_kpi['trend']['direction'] = 'up'
                        elif percent_change < 0:
                            updated_kpi['trend']['direction'] = 'down'
                        else:
                            updated_kpi['trend']['direction'] = 'flat'
            except (ValueError, KeyError) as e:
                print(f"Could not calculate trend for KPI {kpi_name}: {e}")
        
        updated_kpis.append(updated_kpi)
    
    return updated_kpis
