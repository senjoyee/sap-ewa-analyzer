"""
Parameter extraction utility for EWA markdown files.
Extracts recommended parameter changes from markdown tables.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def extract_parameters_from_markdown(md_content: str) -> List[Dict[str, Any]]:
    """
    Extract parameter recommendations from EWA markdown content.
    
    Looks for tables containing parameter information in sections like:
    - SAP HANA Parameters
    - Database Parameters
    - Profile Parameters
    - Application Server Parameters
    - Kernel Parameters
    - System Parameters
    
    Args:
        md_content: Full markdown content of the EWA report
        
    Returns:
        List of parameter dictionaries with keys:
        - parameter_name: Name of the parameter
        - description: Description or purpose
        - area: Database/Application/HANA/Kernel etc.
        - current_value: Current configured value
        - recommended_value: SAP recommended value
        - section: Original section where found
    """
    if not md_content:
        return []
    
    parameters = []
    
    # Split content into sections by headers
    sections = _split_into_sections(md_content)
    
    for section_title, section_content in sections:
        # Determine the area from section title
        area = _determine_area(section_title)
        
        # Skip sections that are unlikely to contain parameters
        if not _is_parameter_section(section_title, section_content):
            continue
        
        # Extract tables from this section
        tables = _extract_tables(section_content)
        
        for table in tables:
            params = _parse_parameter_table(table, area, section_title)
            parameters.extend(params)
    
    # Deduplicate by parameter name (keep first occurrence with most data)
    parameters = _deduplicate_parameters(parameters)
    
    return parameters


def _split_into_sections(md_content: str) -> List[tuple]:
    """Split markdown into (title, content) tuples by headers."""
    sections = []
    
    # Match headers (##, ###, ####)
    header_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
    
    matches = list(header_pattern.finditer(md_content))
    
    if not matches:
        return [("Document", md_content)]
    
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_content)
        content = md_content[start:end].strip()
        sections.append((title, content))
    
    return sections


def _determine_area(section_title: str) -> str:
    """Determine the parameter area from section title."""
    title_lower = section_title.lower()
    
    if any(k in title_lower for k in ["hana", "sap hana"]):
        return "SAP HANA"
    elif any(k in title_lower for k in ["database", "db ", "oracle", "sql server", "maxdb", "ase", "sybase"]):
        return "Database"
    elif any(k in title_lower for k in ["kernel", "disp+work", "dispatcher"]):
        return "SAP Kernel"
    elif any(k in title_lower for k in ["profile", "instance", "default.pfl", "start profile"]):
        return "Profile Parameters"
    elif any(k in title_lower for k in ["application", "app server", "abap", "java"]):
        return "Application"
    elif any(k in title_lower for k in ["memory", "buffer", "cache"]):
        return "Memory/Buffer"
    elif any(k in title_lower for k in ["operating system", "os ", "linux", "windows", "unix"]):
        return "Operating System"
    elif any(k in title_lower for k in ["network", "rfc", "connection"]):
        return "Network"
    else:
        return "General"


def _is_parameter_section(title: str, content: str) -> bool:
    """Check if a section likely contains parameter recommendations."""
    title_lower = title.lower()
    content_lower = content.lower()
    
    # Keywords that indicate parameter content
    param_keywords = [
        "parameter", "profile", "configuration", "setting",
        "recommended", "current value", "target value",
        "hana", "kernel", "abap", "memory", "buffer",
        "rdisp", "ztta", "abap/", "rsdb", "icm/",
        "global.ini", "indexserver.ini", "daemon.ini"
    ]
    
    # Check title
    if any(k in title_lower for k in param_keywords):
        return True
    
    # Check if content has parameter-like patterns
    if re.search(r'[a-z]+/[a-z_]+', content_lower):  # Pattern like abap/heap_area_dia
        return True
    
    # Check for tables with parameter-like headers
    if "|" in content:
        table_header_keywords = ["parameter", "name", "current", "recommended", "value", "setting"]
        if any(k in content_lower for k in table_header_keywords):
            return True
    
    return False


def _extract_tables(content: str) -> List[str]:
    """Extract markdown tables from content."""
    tables = []
    lines = content.split('\n')
    
    current_table = []
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            current_table.append(stripped)
        elif in_table:
            # End of table
            if current_table:
                tables.append('\n'.join(current_table))
            current_table = []
            in_table = False
    
    # Don't forget the last table
    if current_table:
        tables.append('\n'.join(current_table))
    
    return tables


def _parse_parameter_table(table: str, area: str, section: str) -> List[Dict[str, Any]]:
    """Parse a markdown table and extract parameter information."""
    parameters = []
    lines = table.strip().split('\n')
    
    if len(lines) < 2:
        return []
    
    # Parse header row
    header_line = lines[0]
    headers = [h.strip().lower() for h in header_line.split('|') if h.strip()]
    
    # Skip separator line (|---|---|)
    data_start = 1
    if len(lines) > 1 and re.match(r'^\|[\s\-:|]+\|$', lines[1]):
        data_start = 2
    
    # Map common header variations
    header_map = _create_header_map(headers)
    
    # Skip if we don't have minimum required columns (check values, not keys)
    if 'name' not in header_map.values():
        return []
    
    # Parse data rows
    for line in lines[data_start:]:
        cells = [c.strip() for c in line.split('|') if c.strip() or line.count('|') > len(headers)]
        
        # Clean up cells (remove empty first/last from split)
        if line.startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
        
        if not cells or len(cells) < 2:
            continue
        
        param = {
            "parameter_name": "",
            "description": "",
            "area": area,
            "current_value": "",
            "recommended_value": "",
            "section": section,
        }
        
        # Extract values based on header mapping
        for i, cell in enumerate(cells):
            if i >= len(headers):
                break
            
            col_type = header_map.get(headers[i])
            if col_type == 'name':
                param["parameter_name"] = _clean_value(cell)
            elif col_type == 'description':
                param["description"] = _clean_value(cell)
            elif col_type == 'current':
                param["current_value"] = _clean_value(cell)
            elif col_type == 'recommended':
                param["recommended_value"] = _clean_value(cell)
        
        # Only add if we have at least a parameter name
        if param["parameter_name"]:
            # Try to identify parameter vs recommended if not explicit
            if not param["recommended_value"] and not param["current_value"]:
                # Check if any cell looks like a value
                for i, cell in enumerate(cells):
                    if i >= len(headers):
                        break
                    if _looks_like_value(cell) and headers[i] not in header_map:
                        if not param["current_value"]:
                            param["current_value"] = _clean_value(cell)
                        elif not param["recommended_value"]:
                            param["recommended_value"] = _clean_value(cell)
            
            parameters.append(param)
    
    return parameters


def _create_header_map(headers: List[str]) -> Dict[str, str]:
    """Map header names to standardized types."""
    header_map = {}
    
    for header in headers:
        h = header.lower().strip()
        
        # Parameter name variations
        if any(k in h for k in ['parameter', 'name', 'setting', 'profile', 'key']):
            if 'name' not in header_map.values():
                header_map[header] = 'name'
        
        # Description variations
        elif any(k in h for k in ['description', 'desc', 'purpose', 'meaning', 'comment', 'note']):
            header_map[header] = 'description'
        
        # Current value variations
        elif any(k in h for k in ['current', 'actual', 'configured', 'existing', 'old']):
            header_map[header] = 'current'
        
        # Recommended value variations  
        elif any(k in h for k in ['recommended', 'target', 'suggested', 'new', 'optimal', 'sap']):
            header_map[header] = 'recommended'
        
        # Value without qualifier - could be either
        elif h == 'value':
            if 'recommended' not in header_map.values():
                header_map[header] = 'recommended'
            elif 'current' not in header_map.values():
                header_map[header] = 'current'
    
    return header_map


def _clean_value(value: str) -> str:
    """Clean up a cell value."""
    if not value:
        return ""
    
    # Remove markdown formatting
    value = re.sub(r'\*\*(.+?)\*\*', r'\1', value)  # Bold
    value = re.sub(r'\*(.+?)\*', r'\1', value)      # Italic
    value = re.sub(r'`(.+?)`', r'\1', value)        # Code
    
    # Normalize whitespace
    value = ' '.join(value.split())
    
    return value.strip()


def _looks_like_value(cell: str) -> bool:
    """Check if a cell looks like a parameter value."""
    if not cell:
        return False
    
    cell = cell.strip()
    
    # Numeric values
    if re.match(r'^[\d,.\-+]+\s*(KB|MB|GB|TB|ms|s|min|%)?$', cell, re.IGNORECASE):
        return True
    
    # Boolean-like
    if cell.lower() in ['true', 'false', 'yes', 'no', 'on', 'off', 'enabled', 'disabled']:
        return True
    
    # Path-like
    if '/' in cell or '\\' in cell:
        return True
    
    # Short string that's not a sentence
    if len(cell) < 50 and not cell.endswith('.'):
        return True
    
    return False


def _deduplicate_parameters(parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate parameters, keeping the most complete entry."""
    seen = {}
    
    for param in parameters:
        name = param["parameter_name"].lower()
        
        if name not in seen:
            seen[name] = param
        else:
            # Keep the one with more data
            existing = seen[name]
            existing_score = sum(1 for v in existing.values() if v)
            new_score = sum(1 for v in param.values() if v)
            
            if new_score > existing_score:
                seen[name] = param
    
    return list(seen.values())


def parameters_to_json(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert extracted parameters to a JSON-serializable structure.
    
    Returns:
        Dictionary with:
        - total_count: Number of parameters
        - by_area: Parameters grouped by area
        - parameters: Flat list of all parameters
    """
    by_area = {}
    
    for param in parameters:
        area = param.get("area", "General")
        if area not in by_area:
            by_area[area] = []
        by_area[area].append(param)
    
    return {
        "total_count": len(parameters),
        "by_area": by_area,
        "parameters": parameters
    }
