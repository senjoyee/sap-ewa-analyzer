"""
KPI Extractor for EWA Reports

This module provides deterministic Python logic for extracting Key Performance Indicators
from EWA report markdown files and calculating trends by comparing with previous analysis values.

Key Features:
- Parse "Performance Indicators for [SID]" tables from markdown
- Extract numeric values from various formats (ms, %, GB, etc.)
- Calculate trends by comparing current vs previous values
- No AI dependency - pure Python logic
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal


class KPIExtractor:
    """Extracts and processes KPIs from EWA report markdown content"""
    
    def __init__(self):
        self.kpi_patterns = {
            # Common KPI name patterns to standardize
            'response_time': r'(?:avg\.|average)\s*response\s*time',
            'cpu_utilization': r'(?:max\.|maximum)\s*cpu\s*utilization',
            'db_request_time': r'(?:avg\.|average)\s*db\s*request\s*time',
            'memory_consumption': r'(?:hana|memory)\s*(?:table\s*)?memory\s*consumption',
            'dumps': r'abap\s*dumps',
            'support_package': r'support\s*package\s*age'
        }
    
    def extract_kpis_from_markdown(self, markdown_content: str, system_id: str) -> List[Dict[str, Any]]:
        """
        Extract KPIs from the Performance Indicators table in markdown content
        
        Args:
            markdown_content: The full markdown content of the EWA report
            system_id: System ID to look for in table headers
            
        Returns:
            List of KPI dictionaries with name, current_value, and area
        """
        try:
            # Find the Performance Indicators table
            table_content = self._find_performance_indicators_table(markdown_content, system_id)
            if not table_content:
                print(f"No Performance Indicators table found for system {system_id}")
                return []
            
            # Parse the table
            kpis = self._parse_performance_table(table_content)
            print(f"Extracted {len(kpis)} KPIs from Performance Indicators table")
            
            return kpis
            
        except Exception as e:
            print(f"Error extracting KPIs from markdown: {str(e)}")
            return []
    
    def _find_performance_indicators_table(self, markdown_content: str, system_id: str) -> Optional[str]:
        """Find and extract the Performance Indicators table from markdown"""
        
        # Look for various patterns of the Performance Indicators header
        patterns = [
            rf"#+\s*(?:\d+\.?\d*\s+)?Performance\s+Indicators?\s+for\s+{system_id}",
            rf"#+\s*(?:\d+\.?\d*\s+)?Performance\s+Indicators?\s+for\s+ERP",
            rf"Performance\s+Indicators?\s+for\s+{system_id}",
            rf"Performance\s+Indicators?\s+for\s+ERP"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, markdown_content, re.IGNORECASE | re.MULTILINE)
            if match:
                # Extract content from this point until next major heading or end
                start_pos = match.start()
                
                # Find the next major heading (# or ##) or end of content
                next_heading = re.search(r'\n#+\s+(?!Performance\s+Indicators)', 
                                       markdown_content[start_pos:], re.IGNORECASE)
                
                if next_heading:
                    end_pos = start_pos + next_heading.start()
                    table_section = markdown_content[start_pos:end_pos]
                else:
                    table_section = markdown_content[start_pos:]
                
                return table_section
        
        return None
    
    def _parse_performance_table(self, table_content: str) -> List[Dict[str, Any]]:
        """Parse the performance indicators table from markdown"""
        kpis = []
        current_area = ""
        
        # Split into lines and process
        lines = table_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('|---'):
                continue
            
            # Check if this is a table row
            if '|' in line:
                parts = [part.strip() for part in line.split('|')]
                if len(parts) >= 3:  # Area, Indicators, Value (minimum)
                    area = parts[1] if len(parts) > 1 else ""
                    indicator = parts[2] if len(parts) > 2 else ""
                    value = parts[3] if len(parts) > 3 else ""
                    
                    # Skip header rows
                    if indicator.lower() in ['indicators', 'indicator'] or value.lower() == 'value':
                        continue
                    
                    # Update current area if not empty
                    if area and not area.lower() in ['area', '']:
                        current_area = area
                    
                    # Extract KPI if we have indicator and value
                    if indicator and value:
                        kpi = {
                            'name': self._normalize_kpi_name(indicator),
                            'current_value': value,
                            'area': current_area
                        }
                        kpis.append(kpi)
        
        return kpis
    
    def _normalize_kpi_name(self, raw_name: str) -> str:
        """Normalize KPI names for consistency"""
        # Clean up the name
        name = raw_name.strip()
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^(?:avg\.|max\.|min\.)\s*', '', name, flags=re.IGNORECASE)
        
        # Standardize common terms
        standardizations = {
            r'response\s+time\s+in\s+dialog\s+task': 'Average Dialog Response Time',
            r'db\s+request\s+time\s+in\s+dialog\s+task': 'Average DB Request Time in Dialog Task',
            r'cpu\s+utilization\s+on\s+db\s+server': 'Max CPU Utilization on DB Server',
            r'cpu\s+utilization\s+on\s+appl?\.\s*server': 'Max CPU Utilization on Application Server',
            r'hana\s+table\s+memory\s+consumption': 'HANA Table Memory Consumption',
            r'abap\s+dumps?\s*\(weekly\)': 'ABAP Dumps (Weekly)',
            r'support\s+package\s+age\s*\(months\)': 'Support Package Age (Months)'
        }
        
        for pattern, replacement in standardizations.items():
            if re.search(pattern, name, re.IGNORECASE):
                return replacement
        
        return name
    
    def extract_numeric_value(self, value_str: str) -> Optional[float]:
        """Extract numeric value from formatted strings like '629 ms', '34 %', '2,449 GB'"""
        if not value_str:
            return None
        
        try:
            # Remove common units and formatting
            clean_value = re.sub(r'[^\d.,\-]', '', value_str)
            
            # Handle comma thousands separator
            clean_value = clean_value.replace(',', '')
            
            # Convert to float
            return float(clean_value)
            
        except (ValueError, TypeError):
            print(f"Could not extract numeric value from: {value_str}")
            return None
    
    def calculate_trend(self, current_kpis: List[Dict[str, Any]], 
                       previous_kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate trends by comparing current KPIs with previous KPIs
        
        Args:
            current_kpis: List of current KPI dictionaries
            previous_kpis: List of previous KPI dictionaries
            
        Returns:
            List of KPI dictionaries with trend information added
        """
        if not previous_kpis:
            # First analysis - no previous data
            for kpi in current_kpis:
                kpi['trend'] = {
                    'direction': 'none',
                    'description': 'First analysis - no previous data for comparison'
                }
            return current_kpis
        
        # Create lookup for previous values
        previous_lookup = {kpi['name']: kpi for kpi in previous_kpis}
        
        # Calculate trends
        for kpi in current_kpis:
            kpi_name = kpi['name']
            current_value = self.extract_numeric_value(kpi['current_value'])
            
            if kpi_name in previous_lookup:
                previous_value = self.extract_numeric_value(previous_lookup[kpi_name]['current_value'])
                
                if current_value is not None and previous_value is not None:
                    # Calculate trend
                    if current_value > previous_value:
                        direction = 'up'
                        description = f'Increased from previous analysis'
                    elif current_value < previous_value:
                        direction = 'down'
                        description = f'Decreased from previous analysis' 
                    else:
                        direction = 'flat'
                        description = f'No change from previous analysis'
                else:
                    direction = 'none'
                    description = 'Unable to compare values'
            else:
                # New KPI not in previous analysis
                direction = 'none'
                description = 'New KPI - no previous data'
            
            kpi['trend'] = {
                'direction': direction,
                'description': description
            }
        
        return current_kpis
    
    def format_kpis_for_output(self, kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format KPIs for final JSON output"""
        formatted_kpis = []
        
        for kpi in kpis:
            formatted_kpi = {
                'name': kpi['name'],
                'current_value': kpi['current_value'],
                'area': kpi.get('area', 'System Performance'),  # Default area if missing
                'trend': kpi.get('trend', {
                    'direction': 'none',
                    'description': 'No trend data available'
                })
            }
            
            # Add target_value if available (this would need to be extracted separately or configured)
            if 'target_value' in kpi:
                formatted_kpi['target_value'] = kpi['target_value']
            
            formatted_kpis.append(formatted_kpi)
        
        return formatted_kpis
