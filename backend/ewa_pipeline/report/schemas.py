from typing import Literal
from pydantic import BaseModel
from ewa_pipeline.tracking.token_tracker import TokenUsage


class SectionPlanItem(BaseModel):
    section_id: str
    section_title: str
    analysis_focus: str


class OrchestratorPlan(BaseModel):
    tasks: list[SectionPlanItem]
    planning_notes: str = ""


class Remediation(BaseModel):
    action: str
    sap_transactions: list[str]
    effort_estimate: Literal["Low", "Medium", "High"]
    priority: Literal["Immediate", "Short-term", "Medium-term", "Long-term"]


class Finding(BaseModel):
    id: str
    title: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    description: str
    evidence: str
    impact: str
    remediation: Remediation


class DomainAnalysis(BaseModel):
    section_title: str
    section_id: str
    findings: list[Finding]
    overall_health: Literal["Critical", "Warning", "Healthy"]


class CrossReference(BaseModel):
    title: str
    related_findings: list[str]
    correlation_description: str
    combined_impact: str
    recommended_action: str


class CrossReferenceList(BaseModel):
    """Wrapper so with_structured_output can return a list of CrossReferences."""
    items: list[CrossReference]


class SynthesisResult(BaseModel):
    executive_summary: str
    overall_system_health: Literal["Critical", "Warning", "Healthy"]
    top_5_priority_actions: list[str]


class AnalysisResult(BaseModel):
    domain_analyses: list[DomainAnalysis]
    cross_references: list[CrossReference]
    executive_summary: str
    overall_system_health: Literal["Critical", "Warning", "Healthy"]
    top_5_priority_actions: list[str]
    token_usage: TokenUsage
