"""
JSON Merger Utilities for EWA Analysis

This module provides utilities for combining partial JSON extractions from multiple 
document chapters into a unified analysis structure.
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChapterExtraction:
    """Represents the JSON extraction from a single chapter"""
    chapter_title: str
    chapter_number: int
    extraction_json: Dict[str, Any]
    extraction_success: bool = True
    error_message: Optional[str] = None


class JSONMerger:
    """
    Merges partial JSON extractions from multiple chapters into a unified analysis.
    
    Handles deduplication, conflict resolution, and maintains data integrity
    across chapter boundaries.
    """
    
    def __init__(self):
        # Define how to merge different JSON sections
        self.merge_strategies = {
            'system_metadata': self._merge_system_metadata,
            'system_health_overview': self._merge_system_health,
            'executive_summary': self._merge_executive_summary,
            'positive_findings': self._merge_array_sections,
            'key_findings': self._merge_key_findings,
            'recommendations': self._merge_recommendations,
            'kpis': self._merge_array_sections,
            'capacity_outlook': self._merge_capacity_outlook,
            'parameters': self._merge_parameters,
            'overall_risk': self._merge_overall_risk
        }
    
    def merge_chapter_extractions(self, chapter_extractions: List[ChapterExtraction]) -> Dict[str, Any]:
        """
        Merge multiple chapter extractions into a unified JSON structure.
        
        Args:
            chapter_extractions: List of extractions from each chapter
            
        Returns:
            Merged JSON structure
        """
        if not chapter_extractions:
            return self._create_empty_structure()
        
        # Filter out failed extractions
        successful_extractions = [
            ext for ext in chapter_extractions if ext.extraction_success
        ]
        
        if not successful_extractions:
            return self._create_empty_structure()
        
        # Initialize merged structure with schema version
        merged = {
            "schema_version": "1.1",
            "extraction_metadata": {
                "total_chapters": len(chapter_extractions),
                "successful_chapters": len(successful_extractions),
                "failed_chapters": len(chapter_extractions) - len(successful_extractions),
                "chapter_titles": [ext.chapter_title for ext in successful_extractions],
                "merge_timestamp": datetime.now().isoformat()
            }
        }
        
        # Merge each section using appropriate strategy
        for section_name, merge_func in self.merge_strategies.items():
            try:
                merged[section_name] = merge_func(successful_extractions, section_name)
            except Exception as e:
                print(f"Warning: Error merging section '{section_name}': {str(e)}")
                merged[section_name] = self._get_default_value(section_name)
        
        return merged
    
    def _merge_system_metadata(self, extractions: List[ChapterExtraction], section: str) -> Dict[str, Any]:
        """Merge system metadata, preferring first non-null values."""
        merged = {}
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, {})
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if key not in merged and value is not None:
                        merged[key] = value
        
        return merged
    
    def _merge_system_health(self, extractions: List[ChapterExtraction], section: str) -> Dict[str, Any]:
        """Merge system health overview, using worst-case scenario."""
        health_levels = {'good': 3, 'fair': 2, 'poor': 1}
        reverse_levels = {3: 'good', 2: 'fair', 1: 'poor'}
        
        merged = {}
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, {})
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if value in health_levels:
                        current_level = health_levels.get(merged.get(key, 'good'), 3)
                        new_level = health_levels.get(value, 3)
                        # Take the worse rating
                        merged[key] = reverse_levels[min(current_level, new_level)]
        
        return merged
    
    def _merge_executive_summary(self, extractions: List[ChapterExtraction], section: str) -> str:
        """Merge executive summaries into a comprehensive overview."""
        summaries = []
        
        for extraction in extractions:
            summary = extraction.extraction_json.get(section, "")
            if summary and isinstance(summary, str):
                # Add chapter context
                chapter_summary = f"**{extraction.chapter_title}:**\n{summary}"
                summaries.append(chapter_summary)
        
        if summaries:
            return "\n\n".join(summaries)
        return ""
    
    def _merge_array_sections(self, extractions: List[ChapterExtraction], section: str) -> List[Any]:
        """Merge array sections like positive_findings and kpis."""
        merged_items = []
        seen_items = set()
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, [])
            if isinstance(section_data, list):
                for item in section_data:
                    # Create a key for deduplication
                    if isinstance(item, dict):
                        key = str(item.get('area', '')) + str(item.get('description', ''))
                    else:
                        key = str(item)
                    
                    if key not in seen_items:
                        seen_items.add(key)
                        merged_items.append(item)
        
        return merged_items
    
    def _merge_key_findings(self, extractions: List[ChapterExtraction], section: str) -> List[Dict[str, Any]]:
        """Merge key findings with smart deduplication and ID management."""
        merged_findings = []
        seen_findings = set()
        next_id = 1
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, [])
            if isinstance(section_data, list):
                for finding in section_data:
                    if isinstance(finding, dict):
                        # Create deduplication key based on area and core finding
                        dedup_key = (
                            finding.get('area', '').lower().strip(),
                            finding.get('finding', '')[:100].lower().strip()
                        )
                        
                        if dedup_key not in seen_findings:
                            seen_findings.add(dedup_key)
                            
                            # Assign new sequential ID
                            finding_copy = finding.copy()
                            finding_copy['id'] = f"KF-{next_id:03d}"
                            next_id += 1
                            
                            merged_findings.append(finding_copy)
        
        return merged_findings
    
    def _merge_recommendations(self, extractions: List[ChapterExtraction], section: str) -> List[Dict[str, Any]]:
        """Merge recommendations with ID management and priority handling."""
        merged_recommendations = []
        seen_recommendations = set()
        next_id = 1
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, [])
            if isinstance(section_data, list):
                for recommendation in section_data:
                    if isinstance(recommendation, dict):
                        # Create deduplication key
                        dedup_key = (
                            recommendation.get('action', '')[:100].lower().strip(),
                            recommendation.get('responsible_area', '').lower().strip()
                        )
                        
                        if dedup_key not in seen_recommendations:
                            seen_recommendations.add(dedup_key)
                            
                            # Assign new sequential ID
                            rec_copy = recommendation.copy()
                            rec_copy['recommendation_id'] = f"REC-{next_id:03d}"
                            next_id += 1
                            
                            merged_recommendations.append(rec_copy)
        
        return merged_recommendations
    
    def _merge_capacity_outlook(self, extractions: List[ChapterExtraction], section: str) -> Dict[str, Any]:
        """Merge capacity outlook information."""
        merged = {}
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, {})
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if value and (key not in merged or not merged[key]):
                        merged[key] = value
        
        return merged
    
    def _merge_parameters(self, extractions: List[ChapterExtraction], section: str) -> List[Dict[str, Any]]:
        """Merge parameters with deduplication by name and area."""
        merged_params = []
        seen_params = set()
        
        for extraction in extractions:
            section_data = extraction.extraction_json.get(section, [])
            if isinstance(section_data, list):
                for param in section_data:
                    if isinstance(param, dict):
                        # Create deduplication key
                        dedup_key = (
                            param.get('name', '').lower().strip(),
                            param.get('area', '').lower().strip()
                        )
                        
                        if dedup_key not in seen_params:
                            seen_params.add(dedup_key)
                            merged_params.append(param)
        
        return merged_params
    
    def _merge_overall_risk(self, extractions: List[ChapterExtraction], section: str) -> str:
        """Merge overall risk assessment, taking the highest risk level."""
        risk_levels = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        reverse_levels = {1: 'low', 2: 'medium', 3: 'high', 4: 'critical'}
        
        max_risk = 1  # Start with low risk
        
        for extraction in extractions:
            risk = extraction.extraction_json.get(section, 'low')
            if risk in risk_levels:
                max_risk = max(max_risk, risk_levels[risk])
        
        return reverse_levels[max_risk]
    
    def _create_empty_structure(self) -> Dict[str, Any]:
        """Create an empty JSON structure with all required fields."""
        return {
            "schema_version": "1.1",
            "system_metadata": {},
            "system_health_overview": {},
            "executive_summary": "",
            "positive_findings": [],
            "key_findings": [],
            "recommendations": [],
            "kpis": [],
            "capacity_outlook": {},
            "parameters": [],
            "overall_risk": "low",
            "extraction_metadata": {
                "total_chapters": 0,
                "successful_chapters": 0,
                "failed_chapters": 0,
                "chapter_titles": [],
                "merge_timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_default_value(self, section_name: str) -> Any:
        """Get default value for a section in case of merge failure."""
        defaults = {
            'system_metadata': {},
            'system_health_overview': {},
            'executive_summary': "",
            'positive_findings': [],
            'key_findings': [],
            'recommendations': [],
            'kpis': [],
            'capacity_outlook': {},
            'parameters': [],
            'overall_risk': "low"
        }
        return defaults.get(section_name, None)
    
    def get_merge_summary(self, chapter_extractions: List[ChapterExtraction]) -> Dict[str, Any]:
        """Get a summary of the merge process."""
        successful = sum(1 for ext in chapter_extractions if ext.extraction_success)
        failed = len(chapter_extractions) - successful
        
        return {
            "total_chapters": len(chapter_extractions),
            "successful_extractions": successful,
            "failed_extractions": failed,
            "success_rate": f"{(successful / len(chapter_extractions) * 100):.1f}%" if chapter_extractions else "0%",
            "chapter_titles": [ext.chapter_title for ext in chapter_extractions],
            "failed_chapters": [ext.chapter_title for ext in chapter_extractions if not ext.extraction_success]
        }
