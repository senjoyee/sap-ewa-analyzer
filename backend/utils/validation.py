"""
Validation utilities for EWA analysis workflow.
Provides shared validation functions for all agent phases.
"""

import re
from typing import List, Dict, Any, Optional
from jsonschema import validate, ValidationError as JsonSchemaValidationError


class ValidationError(Exception):
    """Custom validation error with phase and error details"""
    def __init__(self, phase: str, errors: List[str]):
        self.phase = phase
        self.errors = errors
        super().__init__(f"Validation failed in {phase}: {'; '.join(errors)}")


def validate_sid(sid: str) -> bool:
    """Validate 3-letter uppercase SID format"""
    if not isinstance(sid, str):
        return False
    return bool(re.match(r'^[A-Z]{3}$', sid))


def validate_date_format(date: str) -> bool:
    """Validate dd.mm.yyyy format"""
    if not isinstance(date, str):
        return False
    return bool(re.match(r'^\d{2}\.\d{2}\.\d{4}$', date))


def validate_finding_id(id_str: str) -> bool:
    """Validate KF-## pattern (e.g., KF-01, KF-02)"""
    if not isinstance(id_str, str):
        return False
    return bool(re.match(r'^KF-\d{2}$', id_str))


def validate_recommendation_id(id_str: str) -> bool:
    """Validate REC-## pattern (e.g., REC-01, REC-02)"""
    if not isinstance(id_str, str):
        return False
    return bool(re.match(r'^REC-\d{2}$', id_str))


def validate_enum(value: str, allowed: List[str], case_sensitive: bool = True) -> bool:
    """Validate value is in allowed enum list"""
    if not isinstance(value, str):
        return False
    if case_sensitive:
        return value in allowed
    return value.lower() in [a.lower() for a in allowed]


def validate_linkage(recommendations: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> List[str]:
    """
    Validate all linked_issue_id references exist in findings.
    Returns list of error messages (empty if valid).
    """
    finding_ids = {f.get("id") for f in findings if f.get("id")}
    errors = []
    
    for rec in recommendations:
        rec_id = rec.get("id", "UNKNOWN")
        linked = rec.get("linked_issue_id")
        
        if linked and linked not in finding_ids:
            errors.append(f"Recommendation {rec_id} links to non-existent finding {linked}")
    
    return errors


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """
    Validate all required fields are present and non-null.
    Returns list of missing field names.
    """
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing.append(field)
    return missing


def validate_no_nulls(data: Dict[str, Any], path: str = "") -> List[str]:
    """
    Recursively check for null values in nested dict.
    Returns list of paths containing nulls.
    """
    null_paths = []
    
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key
        
        if value is None:
            null_paths.append(current_path)
        elif isinstance(value, dict):
            null_paths.extend(validate_no_nulls(value, current_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if item is None:
                    null_paths.append(f"{current_path}[{i}]")
                elif isinstance(item, dict):
                    null_paths.extend(validate_no_nulls(item, f"{current_path}[{i}]"))
    
    return null_paths


def validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    """
    Validate data against JSON schema.
    Returns error message if invalid, None if valid.
    """
    try:
        validate(instance=data, schema=schema)
        return None
    except JsonSchemaValidationError as e:
        return str(e)


def validate_health_ratings(health_overview: Dict[str, Any]) -> List[str]:
    """
    Validate System Health Overview ratings.
    Returns list of validation errors.
    """
    allowed_ratings = ["good", "fair", "poor"]
    required_areas = ["performance", "security", "stability", "configuration"]
    errors = []
    
    for area in required_areas:
        if area not in health_overview:
            errors.append(f"Missing health rating for area: {area}")
        elif not validate_enum(health_overview[area], allowed_ratings):
            errors.append(f"Invalid rating for {area}: {health_overview.get(area)} (must be one of {allowed_ratings})")
    
    return errors


def validate_severity(severity: str) -> bool:
    """Validate severity enum (low, medium, high, critical)"""
    return validate_enum(severity, ["low", "medium", "high", "critical"])


def validate_risk_rating(risk: str) -> bool:
    """Validate overall risk rating (low, medium, high, critical)"""
    return validate_enum(risk, ["low", "medium", "high", "critical"])


def validate_effort_structure(effort: Dict[str, Any]) -> List[str]:
    """
    Validate estimated_effort has both analysis and implementation keys.
    Returns list of validation errors.
    """
    errors = []
    required_keys = ["analysis", "implementation"]
    allowed_values = ["low", "medium", "high"]
    
    for key in required_keys:
        if key not in effort:
            errors.append(f"Missing effort key: {key}")
        elif not validate_enum(effort[key], allowed_values):
            errors.append(f"Invalid effort value for {key}: {effort.get(key)} (must be one of {allowed_values})")
    
    return errors


def validate_medium_high_critical_coverage(findings: List[Dict[str, Any]], recommendations: List[Dict[str, Any]]) -> List[str]:
    """
    Validate each medium/high/critical finding has at least one recommendation.
    Returns list of validation errors.
    """
    errors = []
    critical_finding_ids = {
        f.get("id") for f in findings 
        if f.get("severity") in ["medium", "high", "critical"]
    }
    
    linked_finding_ids = {
        rec.get("linked_issue_id") for rec in recommendations 
        if rec.get("linked_issue_id")
    }
    
    uncovered = critical_finding_ids - linked_finding_ids
    if uncovered:
        errors.append(f"Medium/high/critical findings without recommendations: {', '.join(sorted(uncovered))}")
    
    return errors
