"""
Pillar definitions, routing maps, and display metadata for the 8-Pillar EWA analysis.

This module is the single source of truth for pillar names, display labels,
target personas, and the deterministic keyword-to-pillar routing table.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List


class PillarEnum(str, Enum):
    """The 8 pillars that EWA findings are routed into."""

    EXECUTIVE_SUMMARY = "executive_summary"
    SECURITY_COMPLIANCE = "security_compliance"
    BASIS_OPERATIONS = "basis_operations"
    DATABASE_INFRASTRUCTURE = "database_infrastructure"
    INTEGRATION_CONNECTIVITY = "integration_connectivity"
    LIFECYCLE_UPGRADES = "lifecycle_upgrades"
    BUSINESS_PROCESSES_DVM = "business_processes_dvm"
    UNCATEGORIZED = "uncategorized"


# ── Display names for Excel tab headers ──────────────────────────────────

PILLAR_DISPLAY_NAMES: Dict[str, str] = {
    PillarEnum.EXECUTIVE_SUMMARY:        "Executive Summary",
    PillarEnum.SECURITY_COMPLIANCE:      "Security & Compliance",
    PillarEnum.BASIS_OPERATIONS:         "Basis Core Operations",
    PillarEnum.DATABASE_INFRASTRUCTURE:  "Database & Infrastructure",
    PillarEnum.INTEGRATION_CONNECTIVITY: "Integration & Connectivity",
    PillarEnum.LIFECYCLE_UPGRADES:       "Lifecycle & Upgrades",
    PillarEnum.BUSINESS_PROCESSES_DVM:   "Business Processes & DVM",
    PillarEnum.UNCATEGORIZED:            "Uncategorized",
}

PILLAR_TAB_ICONS: Dict[str, str] = {
    PillarEnum.EXECUTIVE_SUMMARY:        "\U0001f3c6",  # 🏆
    PillarEnum.SECURITY_COMPLIANCE:      "\U0001f6e1\ufe0f",  # 🛡️
    PillarEnum.BASIS_OPERATIONS:         "\u2699\ufe0f",  # ⚙️
    PillarEnum.DATABASE_INFRASTRUCTURE:  "\U0001f4be",  # 💾
    PillarEnum.INTEGRATION_CONNECTIVITY: "\U0001f50c",  # 🔌
    PillarEnum.LIFECYCLE_UPGRADES:       "\U0001f680",  # 🚀
    PillarEnum.BUSINESS_PROCESSES_DVM:   "\U0001f4bc",  # 💼
    PillarEnum.UNCATEGORIZED:            "\u26a0\ufe0f",  # ⚠️
}

# ── Target personas per pillar ───────────────────────────────────────────

PILLAR_PERSONAS: Dict[str, str] = {
    PillarEnum.EXECUTIVE_SUMMARY:        "CTO / VP of IT / Service Delivery Manager",
    PillarEnum.SECURITY_COMPLIANCE:      "CISO / Security Admin",
    PillarEnum.BASIS_OPERATIONS:         "SAP Basis Engineer",
    PillarEnum.DATABASE_INFRASTRUCTURE:  "DBA / Infrastructure Lead",
    PillarEnum.INTEGRATION_CONNECTIVITY: "Middleware / Integration Engineer",
    PillarEnum.LIFECYCLE_UPGRADES:       "Enterprise Architect / Account Manager",
    PillarEnum.BUSINESS_PROCESSES_DVM:   "Functional Consultant / Finance Lead",
    PillarEnum.UNCATEGORIZED:            "Lead Basis Consultant (manual triage)",
}

# ── Deterministic keyword → pillar routing table ─────────────────────────
# Keys are lowercase substrings matched against chapter titles, Area fields,
# and Check Overview topics. Order matters: first match wins.

CHAPTER_KEYWORD_MAP: List[tuple[str, str]] = [
    # Executive Summary
    ("service summary", PillarEnum.EXECUTIVE_SUMMARY),
    ("landscape", PillarEnum.EXECUTIVE_SUMMARY),

    # Security & Compliance
    ("security", PillarEnum.SECURITY_COMPLIANCE),
    ("authorization", PillarEnum.SECURITY_COMPLIANCE),
    ("password", PillarEnum.SECURITY_COMPLIANCE),
    ("sap_all", PillarEnum.SECURITY_COMPLIANCE),
    ("secure configuration", PillarEnum.SECURITY_COMPLIANCE),
    ("tls", PillarEnum.SECURITY_COMPLIANCE),
    ("ssl", PillarEnum.SECURITY_COMPLIANCE),
    ("encryption", PillarEnum.SECURITY_COMPLIANCE),
    ("compliance", PillarEnum.SECURITY_COMPLIANCE),

    # Basis Core Operations
    ("service readiness", PillarEnum.BASIS_OPERATIONS),
    ("hardware capacity", PillarEnum.BASIS_OPERATIONS),
    ("hardware configuration", PillarEnum.BASIS_OPERATIONS),
    ("workload", PillarEnum.BASIS_OPERATIONS),
    ("response time", PillarEnum.BASIS_OPERATIONS),
    ("dialog", PillarEnum.BASIS_OPERATIONS),
    ("abap", PillarEnum.BASIS_OPERATIONS),
    ("dumps", PillarEnum.BASIS_OPERATIONS),
    ("transport", PillarEnum.BASIS_OPERATIONS),
    ("operating system", PillarEnum.BASIS_OPERATIONS),
    ("number ranges", PillarEnum.BASIS_OPERATIONS),
    ("icf service", PillarEnum.BASIS_OPERATIONS),
    ("ui technology", PillarEnum.BASIS_OPERATIONS),
    ("fiori", PillarEnum.BASIS_OPERATIONS),
    ("service data", PillarEnum.BASIS_OPERATIONS),

    # Database & Infrastructure
    ("hana database", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("sap hana", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("database", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("sql statement", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("sql performance", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("db performance", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("backup", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("disk space", PillarEnum.DATABASE_INFRASTRUCTURE),
    ("index", PillarEnum.DATABASE_INFRASTRUCTURE),

    # Integration & Connectivity
    ("rfc", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("gateway", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("idoc", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("interface", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("middleware", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("connectivity", PillarEnum.INTEGRATION_CONNECTIVITY),
    ("netweaver gateway", PillarEnum.INTEGRATION_CONNECTIVITY),

    # Lifecycle & Upgrades
    ("software configuration", PillarEnum.LIFECYCLE_UPGRADES),
    ("upgrade", PillarEnum.LIFECYCLE_UPGRADES),
    ("kernel", PillarEnum.LIFECYCLE_UPGRADES),
    ("end of life", PillarEnum.LIFECYCLE_UPGRADES),
    ("end-of-life", PillarEnum.LIFECYCLE_UPGRADES),
    ("ai scenario", PillarEnum.LIFECYCLE_UPGRADES),
    ("innovation", PillarEnum.LIFECYCLE_UPGRADES),
    ("support package", PillarEnum.LIFECYCLE_UPGRADES),
    ("patch", PillarEnum.LIFECYCLE_UPGRADES),
    ("lifecycle", PillarEnum.LIFECYCLE_UPGRADES),

    # Business Processes & DVM
    ("business key", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("financial", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("data volume", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("archiving", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("cross-application", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("cross application", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("invoice", PillarEnum.BUSINESS_PROCESSES_DVM),
    ("bank statement", PillarEnum.BUSINESS_PROCESSES_DVM),
]


def keyword_route(text: str) -> str | None:
    """Return the pillar key for the first keyword match in *text*, or None."""
    lowered = text.lower()
    for keyword, pillar in CHAPTER_KEYWORD_MAP:
        if keyword in lowered:
            return pillar
    return None


# ── Area (from v1.1 findings) → pillar mapping ──────────────────────────
# These map the "Area" field values produced by the existing v1.1 schema.

AREA_TO_PILLAR_MAP: Dict[str, str] = {
    # Security
    "security": PillarEnum.SECURITY_COMPLIANCE,
    "secure configuration": PillarEnum.SECURITY_COMPLIANCE,

    # Basis
    "service data quality": PillarEnum.BASIS_OPERATIONS,
    "hardware capacity planning": PillarEnum.BASIS_OPERATIONS,
    "hardware configuration": PillarEnum.BASIS_OPERATIONS,
    "workload analysis": PillarEnum.BASIS_OPERATIONS,
    "operating system": PillarEnum.BASIS_OPERATIONS,
    "abap": PillarEnum.BASIS_OPERATIONS,
    "service readiness": PillarEnum.BASIS_OPERATIONS,
    "ui technology": PillarEnum.BASIS_OPERATIONS,

    # Database
    "sap hana database": PillarEnum.DATABASE_INFRASTRUCTURE,
    "sap hana": PillarEnum.DATABASE_INFRASTRUCTURE,
    "database": PillarEnum.DATABASE_INFRASTRUCTURE,
    "sql performance": PillarEnum.DATABASE_INFRASTRUCTURE,

    # Integration
    "rfc load": PillarEnum.INTEGRATION_CONNECTIVITY,
    "sap netweaver gateway": PillarEnum.INTEGRATION_CONNECTIVITY,
    "interface": PillarEnum.INTEGRATION_CONNECTIVITY,

    # Lifecycle
    "software configuration": PillarEnum.LIFECYCLE_UPGRADES,
    "upgrade planning": PillarEnum.LIFECYCLE_UPGRADES,
    "ai scenarios": PillarEnum.LIFECYCLE_UPGRADES,

    # Business Processes
    "business key figures": PillarEnum.BUSINESS_PROCESSES_DVM,
    "financial data quality": PillarEnum.BUSINESS_PROCESSES_DVM,
    "data volume management": PillarEnum.BUSINESS_PROCESSES_DVM,
    "cross-application checks": PillarEnum.BUSINESS_PROCESSES_DVM,
}


def area_to_pillar(area: str) -> str | None:
    """Map a v1.1 Area field value to a pillar, or None if no match."""
    lowered = area.strip().lower()
    if lowered in AREA_TO_PILLAR_MAP:
        return AREA_TO_PILLAR_MAP[lowered]
    # Fallback: try keyword routing on the area text
    return keyword_route(area)


# ── Parameter area → pillar mapping ──────────────────────────────────────
# Maps the parameter_extraction_schema "area" enum to pillars.

PARAM_AREA_TO_PILLAR: Dict[str, str] = {
    "sap hana": PillarEnum.DATABASE_INFRASTRUCTURE,
    "database": PillarEnum.DATABASE_INFRASTRUCTURE,
    "sap kernel": PillarEnum.LIFECYCLE_UPGRADES,
    "profile parameters": PillarEnum.BASIS_OPERATIONS,
    "application": PillarEnum.BASIS_OPERATIONS,
    "memory/buffer": PillarEnum.BASIS_OPERATIONS,
    "operating system": PillarEnum.BASIS_OPERATIONS,
    "network": PillarEnum.INTEGRATION_CONNECTIVITY,
    "general": PillarEnum.BASIS_OPERATIONS,
}


# ── Responsible Area → assignee_group shorthand ──────────────────────────

RESPONSIBLE_AREA_TO_ASSIGNEE: Dict[str, str] = {
    "SAP Basis Team": "Basis",
    "Database Administration": "DBA",
    "Operating System Administration": "OS Admin",
    "Network & Connectivity": "Network",
    "Security / Compliance Team": "SecOps",
    "Application Development": "AppDev",
    "Functional / Business Process Owner": "Functional",
    "Infrastructure / Hardware Team": "Infra",
    "Third-Party Vendor": "Vendor",
    "Project / Change Management": "PM/Change",
}


# ── Empty pillar template ────────────────────────────────────────────────

def empty_pillar() -> dict:
    """Return an empty PillarContent structure."""
    return {"findings": [], "positives": [], "recommendations": []}


def empty_pillars() -> dict:
    """Return a dict of all 8 pillars with empty content."""
    return {p.value: empty_pillar() for p in PillarEnum}


# ── All pillar keys in display order ─────────────────────────────────────

PILLAR_ORDER: List[str] = [
    PillarEnum.EXECUTIVE_SUMMARY,
    PillarEnum.SECURITY_COMPLIANCE,
    PillarEnum.BASIS_OPERATIONS,
    PillarEnum.DATABASE_INFRASTRUCTURE,
    PillarEnum.INTEGRATION_CONNECTIVITY,
    PillarEnum.LIFECYCLE_UPGRADES,
    PillarEnum.BUSINESS_PROCESSES_DVM,
    PillarEnum.UNCATEGORIZED,
]
