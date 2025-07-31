"""
Test script for validating KPI extraction and trend calculation
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.kpi_extractor import KPIExtractor
import json

def test_kpi_extraction():
    """Test KPI extraction from sample markdown content"""
    
    # Sample markdown content with Performance Indicators table
    sample_markdown = """
# SAP EarlyWatch Alert Report

## 1. Executive Summary

## 2. Performance Indicators for ERP

| Area | Indicators | Value |
|------|------------|-------|
| Workload | Avg. Response Time in Dialog Task | 629 ms |
| Workload | Max. CPU Utilization on Appl. Server | 34 % |
| Workload | Avg. DB Request Time in Dialog Task | 38 ms |
| Database | Max CPU Utilization on DB Server | 23 % |
| Database | HANA Table Memory Consumption | 2,449 GB |
| System | ABAP Dumps (weekly) | 2 |
| System | Support Package Age (months) | 18 |

## 3. Key Findings

## 4. Recommendations
"""
    
    # Initialize extractor
    extractor = KPIExtractor()
    
    # Extract KPIs
    kpis = extractor.extract_kpis_from_markdown(sample_markdown, "ERP")
    
    print(f"Extracted {len(kpis)} KPIs:")
    for kpi in kpis:
        print(f"  - {kpi['name']}: {kpi['current_value']} (Area: {kpi['area']})")
    
    return kpis

def test_trend_calculation():
    """Test trend calculation with sample data"""
    
    # Current KPIs
    current_kpis = [
        {'name': 'Average Dialog Response Time', 'current_value': '629 ms', 'area': 'Workload'},
        {'name': 'Max CPU Utilization on Application Server', 'current_value': '34 %', 'area': 'Workload'},
        {'name': 'Average DB Request Time in Dialog Task', 'current_value': '38 ms', 'area': 'Workload'}
    ]
    
    # Previous KPIs (from a previous analysis)
    previous_kpis = [
        {'name': 'Average Dialog Response Time', 'current_value': '528 ms'},
        {'name': 'Max CPU Utilization on Application Server', 'current_value': '34 %'},
        {'name': 'Average DB Request Time in Dialog Task', 'current_value': '45 ms'}
    ]
    
    # Initialize extractor
    extractor = KPIExtractor()
    
    # Calculate trends
    kpis_with_trends = extractor.calculate_trend(current_kpis, previous_kpis)
    
    print("\nKPIs with trends:")
    for kpi in kpis_with_trends:
        trend = kpi.get('trend', {})
        print(f"  - {kpi['name']}: {kpi['current_value']} -> {trend.get('direction', 'none')} ({trend.get('description', '')})")
    
    return kpis_with_trends

def test_first_analysis():
    """Test first analysis with no previous data"""
    
    # Current KPIs (first analysis)
    current_kpis = [
        {'name': 'Average Dialog Response Time', 'current_value': '528 ms', 'area': 'Workload'},
        {'name': 'Max CPU Utilization on Application Server', 'current_value': '34 %', 'area': 'Workload'}
    ]
    
    # No previous KPIs
    previous_kpis = []
    
    # Initialize extractor
    extractor = KPIExtractor()
    
    # Calculate trends
    kpis_with_trends = extractor.calculate_trend(current_kpis, previous_kpis)
    
    print("\nFirst analysis KPIs (no previous data):")
    for kpi in kpis_with_trends:
        trend = kpi.get('trend', {})
        print(f"  - {kpi['name']}: {kpi['current_value']} -> {trend.get('direction', 'none')} ({trend.get('description', '')})")
    
    return kpis_with_trends

def test_numeric_extraction():
    """Test numeric value extraction from various formats"""
    
    extractor = KPIExtractor()
    
    test_values = [
        '629 ms',
        '34 %',
        '2,449 GB',
        '2',
        '18 months',
        '0.5 sec'
    ]
    
    print("\nNumeric value extraction:")
    for value_str in test_values:
        numeric_value = extractor.extract_numeric_value(value_str)
        print(f"  - '{value_str}' -> {numeric_value}")

def main():
    """Run all tests"""
    print("=== KPI Extractor Validation Tests ===\n")
    
    # Test 1: KPI extraction
    extracted_kpis = test_kpi_extraction()
    
    # Test 2: Numeric value extraction
    test_numeric_extraction()
    
    # Test 3: Trend calculation
    kpis_with_trends = test_trend_calculation()
    
    # Test 4: First analysis (no previous data)
    first_analysis_kpis = test_first_analysis()
    
    print("\n=== Test Summary ===")
    print(f"Extracted KPIs: {len(extracted_kpis)}")
    print(f"KPIs with trends: {len(kpis_with_trends)}")
    print(f"First analysis KPIs: {len(first_analysis_kpis)}")

if __name__ == "__main__":
    main()
