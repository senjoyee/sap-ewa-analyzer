"""
Test script for KPI trend tracking functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import json
from utils.kpi_utils import update_kpi_trends

def test_kpi_trends():
    # Test data
    current_kpis = [
        {"name": "CPU Utilization", "current_value": "75.5%"},
        {"name": "Memory Usage", "current_value": "12.3 GB"},
        {"name": "Disk I/O", "current_value": "1500 ops/sec"},
        {"name": "New Relic Score", "current_value": "85"}
    ]
    
    previous_kpis = [
        {"name": "CPU Utilization", "current_value": "68.2%"},
        {"name": "Memory Usage", "current_value": "10.1 GB"},
        {"name": "Disk I/O", "current_value": "1500 ops/sec"},
        {"name": "Network Latency", "current_value": "45 ms"}
    ]
    
    # Update trends
    updated_kpis = update_kpi_trends(current_kpis, previous_kpis)
    
    # Print results
    print("KPI Trends Analysis:")
    print("===================")
    for kpi in updated_kpis:
        name = kpi['name']
        value = kpi['current_value']
        trend = kpi.get('trend', {})
        direction = trend.get('direction', 'N/A')
        percent_change = trend.get('percent_change', 'N/A')
        
        print(f"{name}: {value}")
        print(f"  Trend: {direction}")
        if percent_change != 'N/A':
            print(f"  Change: {percent_change}%")
        print()
    
    # Verify expected results
    cpu_kpi = next(k for k in updated_kpis if k['name'] == 'CPU Utilization')
    assert cpu_kpi['trend']['direction'] == 'up'
    assert cpu_kpi['trend']['percent_change'] > 0
    
    memory_kpi = next(k for k in updated_kpis if k['name'] == 'Memory Usage')
    assert memory_kpi['trend']['direction'] == 'up'
    assert memory_kpi['trend']['percent_change'] > 0
    
    disk_kpi = next(k for k in updated_kpis if k['name'] == 'Disk I/O')
    assert disk_kpi['trend']['direction'] == 'flat'
    
    new_relic_kpi = next(k for k in updated_kpis if k['name'] == 'New Relic Score')
    assert new_relic_kpi['trend']['direction'] == 'flat'  # No previous data
    
    print("All tests passed!")

if __name__ == "__main__":
    test_kpi_trends()
