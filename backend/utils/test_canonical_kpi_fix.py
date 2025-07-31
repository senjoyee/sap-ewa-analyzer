"""
Test to validate the canonical KPI list bug fix
"""

def test_canonical_kpi_handling():
    """Test handling of canonical KPI list with mixed types"""
    
    # Simulate the problematic canonical data that caused the error
    canonical_data_with_dicts = {
        'kpi_list': [
            {'name': 'Average Dialog Response Time', 'other_field': 'value'},
            {'name': 'Max CPU Utilization on Application Server'},
            'HANA Table Memory Consumption',  # String format
            {'name': 'ABAP Dumps (Weekly)'},
            'Support Package Age (Months)',  # String format
            {'malformed': 'entry'},  # Malformed dict without 'name'
        ]
    }
    
    # Test the fixed logic (same as in workflow_orchestrator.py)
    canonical_kpi_list = canonical_data_with_dicts.get('kpi_list', [])
    canonical_names = set()
    
    for item in canonical_kpi_list:
        if isinstance(item, str):
            canonical_names.add(item)
        elif isinstance(item, dict) and 'name' in item:
            canonical_names.add(item['name'])
        elif isinstance(item, dict):
            # Skip malformed entries
            print(f"Warning: Skipping malformed canonical KPI entry: {item}")
    
    print("Canonical KPI names extracted:")
    for name in sorted(canonical_names):
        print(f"  - {name}")
    
    # Test current KPIs comparison
    current_kpis = [
        {'name': 'Average Dialog Response Time'},
        {'name': 'Max CPU Utilization on Application Server'},
        {'name': 'HANA Table Memory Consumption'},
        {'name': 'New KPI Not in List'},  # This should be detected as new
    ]
    
    current_names = set(kpi.get('name', '') for kpi in current_kpis if kpi.get('name'))
    
    new_kpis = current_names - canonical_names
    
    print(f"\nComparison results:")
    print(f"Canonical KPIs: {len(canonical_names)}")
    print(f"Current KPIs: {len(current_names)}")
    print(f"New KPIs detected: {list(new_kpis)}")
    
    return len(canonical_names) > 0 and len(new_kpis) == 1

if __name__ == "__main__":
    print("=== Testing Canonical KPI List Bug Fix ===\n")
    
    success = test_canonical_kpi_handling()
    
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
