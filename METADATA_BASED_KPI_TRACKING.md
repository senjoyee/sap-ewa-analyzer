# Metadata-Based KPI Tracking Implementation

## Overview
This document describes the implementation of metadata-based KPI tracking in the EWA Analyzer, which uses blob metadata instead of filename conventions to identify customer and system information for trend analysis.

## Key Changes

### 1. Modified `extract_customer_system_from_blob_name` Function
The function now prioritizes retrieving customer and system information from blob metadata before falling back to filename parsing.

```python
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
    # ... (existing filename parsing logic)
```

### 2. Updated `get_previous_kpi_data` Function
The function now accepts an optional `blob_service_client` parameter to avoid creating multiple connections.

### 3. Modified Workflow Orchestrator
Updated calls to pass the blob service client to the utility functions:

```python
# In workflow_orchestrator.py
from utils.kpi_utils import extract_customer_system_from_blob_name, get_previous_kpi_data
customer, system = extract_customer_system_from_blob_name(state.blob_name, self.blob_service_client)
previous_kpis, canonical_kpi_names = get_previous_kpi_data(customer, system, state.blob_name, self.blob_service_client)
```

## Benefits of Metadata-Based Approach

1. **More Reliable**: Metadata is explicitly set and doesn't depend on filename formatting
2. **Flexible Naming**: Files can be named however users prefer
3. **Already Available**: Customer name metadata is already being set during upload
4. **Automatic Values**: System ID and report date are automatically extracted from AI analysis
5. **Chronologically Accurate**: Uses actual report dates rather than file creation times for trend analysis
6. **Extensible**: Easy to add more metadata fields like report type, version, etc.

## Metadata Requirements

For the metadata-based approach to work, the following metadata should be set on blobs:

- `customer`: The customer name
- `system_id` or `system`: The system identifier
- `report_date`: The date of the EWA report

If this metadata is not available, the system will still work correctly as it now automatically extracts the system ID and report date from the AI analysis output and adds it back to the blob metadata for future use.

## Fallback Mechanism

If metadata is not available, the system falls back to the original filename parsing approach:

```
Expected format: <customer>_<system>_<date>_<report_type>.<extension>
Example: ACME_PRD_20250718_EWA.pdf
```

## Implementation Status

- ✅ Modified utility functions to use metadata
- ✅ Updated workflow orchestrator to pass blob service client
- ✅ Maintained backward compatibility with filename parsing
- ✅ Enhanced system to automatically extract and persist system_id from AI analysis
- ✅ Enhanced system to automatically extract and persist report_date from AI analysis
- ✅ Modified trend analysis to use report_date metadata for selecting previous analysis
- ✅ Tested functionality

## Future Enhancements

1. Update documentation to reflect the new metadata-based approach
2. Add validation to ensure required metadata is present
3. Add support for additional metadata fields like report type, version, etc.
