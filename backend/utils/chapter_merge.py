"""
Utility functions for merging chapter-level analyses into a final EWA summary.
"""

from typing import Dict, Any, List
import re


def merge_chapter_analyses(
    chapter_analyses: List[Dict[str, Any]],
    system_metadata: Dict[str, Any],
    chapters_reviewed: List[str]
) -> Dict[str, Any]:
    """Merge multiple chapter-level analyses into a final EWA summary.
    
    Args:
        chapter_analyses: List of chapter analysis results
        system_metadata: System metadata (SID, report date, etc.)
        chapters_reviewed: List of chapter titles that were reviewed
        
    Returns:
        Complete EWA summary conforming to ewa_summary_schema.json
    """
    print(f"[ChapterMerge] Merging {len(chapter_analyses)} chapter analyses")
    
    # Initialize result structure
    result = {
        "Schema Version": "1.1",
        "System Metadata": system_metadata,
        "Chapters Reviewed": chapters_reviewed,
        "System Health Overview": _derive_health_overview(chapter_analyses),
        "Executive Summary": _generate_executive_summary(chapter_analyses),
        "Positive Findings": _merge_positive_findings(chapter_analyses),
        "Key Findings": _merge_key_findings(chapter_analyses),
        "Recommendations": _merge_recommendations(chapter_analyses),
        "Capacity Outlook": _derive_capacity_outlook(chapter_analyses),
        "Overall Risk": _derive_overall_risk(chapter_analyses)
    }
    
    print(f"[ChapterMerge] Final result: {len(result['Key Findings'])} findings, "
          f"{len(result['Recommendations'])} recommendations")
    
    return result


def _derive_health_overview(chapter_analyses: List[Dict[str, Any]]) -> Dict[str, str]:
    """Derive system health overview from chapter findings."""
    # Count severity levels across all chapters
    severity_counts = {"critical": 0, "high": 0, "medium": 0}
    area_findings = {
        "performance": [],
        "security": [],
        "stability": [],
        "configuration": []
    }
    
    for chapter in chapter_analyses:
        for finding in chapter.get("key_findings", []):
            severity = finding.get("severity", "medium").lower()
            area = finding.get("area", "").lower()
            
            if severity in severity_counts:
                severity_counts[severity] += 1
            
            # Map areas to health categories
            if "performance" in area or "workload" in area:
                area_findings["performance"].append(severity)
            if "security" in area or "compliance" in area:
                area_findings["security"].append(severity)
            if "stability" in area or "backup" in area or "recovery" in area:
                area_findings["stability"].append(severity)
            if "configuration" in area or "house-keeping" in area:
                area_findings["configuration"].append(severity)
    
    # Derive ratings based on findings
    def rate_area(findings):
        if not findings:
            return "good"
        if "critical" in findings or findings.count("high") >= 2:
            return "poor"
        if "high" in findings or findings.count("medium") >= 3:
            return "fair"
        return "good"
    
    return {
        "Performance": rate_area(area_findings["performance"]),
        "Security": rate_area(area_findings["security"]),
        "Stability": rate_area(area_findings["stability"]),
        "configuration": rate_area(area_findings["configuration"])
    }


def _generate_executive_summary(chapter_analyses: List[Dict[str, Any]]) -> str:
    """Generate executive summary from chapter findings."""
    all_findings = []
    critical_count = 0
    high_count = 0
    
    for chapter in chapter_analyses:
        for finding in chapter.get("key_findings", []):
            severity = finding.get("severity", "medium").lower()
            if severity == "critical":
                critical_count += 1
            elif severity == "high":
                high_count += 1
            all_findings.append(finding)
    
    # Build summary
    summary_points = []
    
    # Overall status
    if critical_count > 0:
        summary_points.append(f"Critical: {critical_count} critical issue(s) require immediate attention")
    if high_count > 0:
        summary_points.append(f"High Priority: {high_count} high-severity finding(s) identified")
    
    # Top areas of concern (by frequency)
    area_counts = {}
    for finding in all_findings:
        area = finding.get("area", "Unknown")
        area_counts[area] = area_counts.get(area, 0) + 1
    
    if area_counts:
        top_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        areas_text = ", ".join([f"{area} ({count})" for area, count in top_areas])
        summary_points.append(f"Key areas requiring attention: {areas_text}")
    
    # Positive note
    positive_count = sum(len(ch.get("positive_findings", [])) for ch in chapter_analyses)
    if positive_count > 0:
        summary_points.append(f"{positive_count} positive finding(s) highlight areas of good performance")
    
    # Action summary
    rec_count = sum(len(ch.get("recommendations", [])) for ch in chapter_analyses)
    summary_points.append(f"{rec_count} actionable recommendation(s) provided for remediation")
    
    return "- " + "\n- ".join(summary_points)


def _merge_positive_findings(chapter_analyses: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Merge positive findings from all chapters."""
    findings = []
    seen = set()
    
    for chapter in chapter_analyses:
        for finding in chapter.get("positive_findings", []):
            # Deduplicate based on area + description
            key = f"{finding.get('area', '')}:{finding.get('description', '')}"
            if key not in seen:
                findings.append({
                    "Area": finding.get("area", ""),
                    "Description": finding.get("description", "")
                })
                seen.add(key)
    
    return findings


def _merge_key_findings(chapter_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge and renumber key findings from all chapters."""
    findings = []
    finding_counter = 1
    
    for chapter in chapter_analyses:
        chapter_id = chapter.get("chapter_id", "")
        chapter_title = chapter.get("chapter_title", "")
        
        for finding in chapter.get("key_findings", []):
            # Renumber with global ID
            global_id = f"KF-{finding_counter:02d}"
            
            # Add chapter context to source if not already present
            source = finding.get("source", "")
            if chapter_title and chapter_title not in source:
                source = f"{chapter_title} - {source}" if source else chapter_title
            
            merged_finding = {
                "Issue ID": global_id,
                "Area": finding.get("area", ""),
                "Finding": finding.get("finding", ""),
                "Impact": finding.get("impact", ""),
                "Business impact": finding.get("business_impact", ""),
                "Severity": finding.get("severity", "medium"),
                "Source": source
            }
            
            findings.append(merged_finding)
            finding_counter += 1
    
    return findings


def _merge_recommendations(chapter_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge and renumber recommendations from all chapters, linking to global finding IDs."""
    recommendations = []
    rec_counter = 1
    
    # Build mapping from chapter-local finding IDs to global IDs
    finding_id_map = {}
    global_finding_counter = 1
    
    for chapter in chapter_analyses:
        chapter_id = chapter.get("chapter_id", "")
        for finding in chapter.get("key_findings", []):
            local_id = finding.get("finding_id", "")
            global_id = f"KF-{global_finding_counter:02d}"
            finding_id_map[f"{chapter_id}:{local_id}"] = global_id
            global_finding_counter += 1
    
    # Process recommendations
    for chapter in chapter_analyses:
        chapter_id = chapter.get("chapter_id", "")
        
        for rec in chapter.get("recommendations", []):
            global_rec_id = f"REC-{rec_counter:02d}"
            
            # Map local finding ID to global ID
            local_linked_id = rec.get("linked_finding_id", "")
            global_linked_id = finding_id_map.get(f"{chapter_id}:{local_linked_id}", "KF-01")
            
            merged_rec = {
                "Recommendation ID": global_rec_id,
                "Estimated Effort": rec.get("estimated_effort", {"analysis": "low", "implementation": "low"}),
                "Responsible Area": rec.get("responsible_area", "SAP Basis Team"),
                "Linked issue ID": global_linked_id,
                "Action": rec.get("action", ""),
                "Preventative Action": rec.get("preventative_action", "")
            }
            
            recommendations.append(merged_rec)
            rec_counter += 1
    
    return recommendations


def _derive_capacity_outlook(chapter_analyses: List[Dict[str, Any]]) -> Dict[str, str]:
    """Derive capacity outlook from chapter metrics."""
    # Look for capacity-related metrics across chapters
    db_growth_info = []
    cpu_info = []
    memory_info = []
    
    for chapter in chapter_analyses:
        for metric in chapter.get("metrics", []):
            name = metric.get("name", "").lower()
            value = metric.get("value", "")
            context = metric.get("context", "")
            
            if "database" in name or "db" in name or "growth" in name:
                db_growth_info.append(f"{metric.get('name', '')}: {value}")
            elif "cpu" in name or "processor" in name:
                cpu_info.append(f"{metric.get('name', '')}: {value}")
            elif "memory" in name or "ram" in name:
                memory_info.append(f"{metric.get('name', '')}: {value}")
    
    # Build capacity outlook
    return {
        "Database Growth": "; ".join(db_growth_info) if db_growth_info else "No specific database growth metrics identified",
        "CPU Utilization": "; ".join(cpu_info) if cpu_info else "CPU utilization data to be reviewed from performance chapter",
        "Memory Utilization": "; ".join(memory_info) if memory_info else "Memory utilization data to be reviewed from performance chapter",
        "Summary": "Capacity planning should be based on metrics found in the Performance and Database chapters. Regular monitoring recommended."
    }


def _derive_overall_risk(chapter_analyses: List[Dict[str, Any]]) -> str:
    """Derive overall risk rating from chapter findings."""
    critical_count = 0
    high_count = 0
    medium_count = 0
    
    for chapter in chapter_analyses:
        for finding in chapter.get("key_findings", []):
            severity = finding.get("severity", "medium").lower()
            if severity == "critical":
                critical_count += 1
            elif severity == "high":
                high_count += 1
            elif severity == "medium":
                medium_count += 1
    
    # Determine overall risk
    if critical_count >= 1:
        return "critical"
    elif high_count >= 3:
        return "high"
    elif high_count >= 1 or medium_count >= 5:
        return "medium"
    else:
        return "low"
