# EWA Analysis for BIP (09.11.2025)
**Analysis Period:** 03.11.2025 / 09.11.2025
**Overall Risk Assessment:** `high`

---

## System Health Overview
| Area | Status |
| ---|--- |
| Performance | fair |
| Security | poor |
| Stability | fair |
| Configuration | poor |

---

## Executive Summary
- SAP HANA support package stack for SID HAP (2.00.059.11 / 2.00.059.08 indicated) will reach or has reached end of security maintenance within the next 51 days; upgrade required to mitigate missing security fixes and future unsupported vulnerabilities.
- SAP HANA: user SYSTEM is active — immediate hardening (or deactivation after replacement) and audit activation recommended to close a high-risk privilege gap.
- RFC Gateway ACLs (gw/sec_info / gw/reg_info) are missing or contain trivial entries and gw/acl_mode=0 — the RFC interface is effectively unprotected; treat as critical risk and implement ACLs and set gw/acl_mode=1.
- BW / BIP: severe BW findings (large number of InfoProviders with >10k/ >15k requests, very high query/workload on many InfoProviders) are causing severe performance pressure; high-impact queries and plan buffers identified; immediate query & OLAP cache / aggregate action required.
- BEx frontends: Excel-based BEx tools were out of mainstream support as of 14.10.2025 and large number (820) of BEx workbooks remain in use; plan migration to Analysis for Office or SAC integrations.
- Multiple Basis components and ST-PI add-ons are behind recommended support package levels (several SAP_ABA/SAP_BASIS / ST-PI items older) — implement support package maintenance and the System Recommendations / System Recommendations app.
- TREXviaDBSL / TREX-related HANA calls and several heavy SQL statements (CALL SYS.TREXviaDBSL, large INSERT/LOAD DTP statements) dominate CPU and memory usage during peak hours — tune BIA/BW loads and optimize queries/process chains or schedule heavy loads off-peak.
- Diagnostics & operations: EWA data is not sent to the SAP Backbone; enhanced monitoring for cloud hosts is inactive; global consistency check is not configured (only lightweight checks) — correct to enable SAP remote support & diagnostics and ensure full global consistency checks.
- Overall immediate priorities: HANA security/patching, RFC Gateway hardening, remove/secure SYSTEM, remediate critical authorizations in ABAP clients, and BW query / InfoProvider tuning to relieve HANA pressure.

---

<div style='page-break-before: always;'></div>

## Positive Findings
| Area | Description |
| ---|--- |
| Hardware Capacity | No CPU or memory bottlenecks detected on hosts; Max CPU utilization observed 31% on DB and App servers — headroom exists. |
| SAP Kernel / Basis | SAP Kernel Release 753 PL1500 is up to date (age 5 months). |
| Backup & Recovery | Daily data and log backups succeeded during the analyzed period; automated log backups in place. |
| Row/Column store sizing | Column/row store and partitioning appear stable; no immediate disk space shortage (DATA partition ~26.5% free threshold >20%). |


---

## Key Findings & Recommendations

```json
{
  "layout": "cards",
  "cardType": "merged_findings_recommendations",
  "sectionTitle": "Key Findings & Recommendations",
  "items": [
    {
      "Issue ID": "KF-01",
      "Area": "SAP HANA",
      "Severity": "critical",
      "Source": "Software Configuration for BIP -> HANA Database Support Package Stack; Security -> Maintenance Status of current SAP HANA Database Revision",
      "Finding": "SAP HANA support package stack (HAP 2.00.059.x) is at a revision that will run out of security maintenance within the next 51 days; HANA revision and SP strategy not current.",
      "Impact": "Missing security fixes — exposure to known and unseen vulnerabilities; SAP may no longer provide fixes or analysis for this revision.",
      "Business impact": "High risk of data breach or service interruption; potential non-compliance and remediation costs; regulatory exposure.",
      "Estimated Effort": {
        "analysis": "medium",
        "implementation": "high"
      },
      "Responsible Area": "Infrastructure / Hardware Team",
      "Action": "1) Plan and execute an upgrade of SAP HANA to a supported maintenance revision (move to latest SAP HANA 2.0 revision/SP that is in maintenance). 2) Test the upgrade in a non-production tenant DB (system DB + tenant testing) following SAP Note 2378962 and 2115815. 3) Validate application (BW/BIP) behavior, TREX and client connectivity post-upgrade.\n\n- Ensure upgrade window is scheduled, full backups taken and restore validation performed before upgrade. - Coordinate with BW owners to retest critical queries and process chains.",
      "Preventative Action": "Maintain an annual HANA maintenance cadence (at least once per year for long-term support, faster for standard SPs); subscribe to SAP HANA revision/maintenance SAP Notes and include HANA upgrades in the maintenance calendar."
    },
    {
      "Issue ID": "KF-02",
      "Area": "SAP HANA",
      "Severity": "critical",
      "Source": "Security -> Activation Status and Validity of User SYSTEM",
      "Finding": "User SYSTEM in HANA is active and valid.",
      "Impact": "SYSTEM is a super user that cannot have authorizations revoked — prime target for misuse if credentials are compromised.",
      "Business impact": "Critical administrative privilege risk; potential full-database compromise and unauthorized data access.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "Database Administration",
      "Action": "1) Immediately review and remove/replace usage of user SYSTEM. 2) Create a documented technical user and roles to cover required administrative tasks and migrate operations. 3) Deactivate SYSTEM after testing using: ALTER USER SYSTEM DEACTIVATE USER NOW (only after replacement verified).\n\n- Enable HANA auditing for actions related to SYSTEM and other high-privilege users; review audit logs for prior usage.",
      "Preventative Action": "Define and enforce a privileged-access management process for database super-users; monthly audit of active super-users and enforce least privilege."
    },
    {
      "Issue ID": "KF-03",
      "Area": "Security & Compliance",
      "Severity": "critical",
      "Source": "Security -> RFC Gateway Security; gw/acl_mode and gw/sec_info gw/reg_info checks",
      "Finding": "RFC Gateway ACLs (sec_info / reg_info) are not configured correctly; gw/acl_mode = 0 and secinfo files missing or containing trivial entries.",
      "Impact": "RFC gateway will accept unwanted connections (simulation mode or no ACL protection), enabling unauthorized RFC access.",
      "Business impact": "High risk of lateral movement into SAP, data exfiltration, or system manipulation via RFC channels.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "SAP Basis Team",
      "Action": "1) Implement RFC Gateway access control lists (gw/sec_info and gw/reg_info) with non-trivial entries via SMGW and set gw/acl_mode = 1 in profiles. 2) Set gw/sim_mode = 0 and verify ACL files exist and are restrictive. 3) Test RFC connections after change during maintenance window.\n\n- Apply transaction SMGW to maintain secinfo/reginfo files and restrict by host/service/user patterns as per SAP Note 1408081 / 1305851.",
      "Preventative Action": "Add ACL file checks to system hardening checklist and monitor gateway logs for unauthorized attempts; include in monthly security reviews."
    },
    {
      "Issue ID": "KF-04",
      "Area": "ABAP Stack",
      "Severity": "high",
      "Source": "Security -> Critical authorizations sections (SAP_ALL counts per client; Debug authorizations)",
      "Finding": "Many users with critical authorizations (SAP_ALL and debug / replace privileges) across clients including client 000 and production clients.",
      "Impact": "Excessive privileges increase the likelihood of accidental or malicious privileged actions; bypass authorization checks via debug.",
      "Business impact": "High risk to systems and data integrity; audit & compliance failures; potential for unauthorized changes.",
      "Estimated Effort": {
        "analysis": "medium",
        "implementation": "medium"
      },
      "Responsible Area": "Security / Compliance Team",
      "Action": "1) Run an authorization cleanup project: extract roles with SAP_ALL, S_DEVELOP debug privileges and S_TCODE SU01/OIBB usage (SUIM). 2) Remove unnecessary SAP_ALL and DEBUG from production roles; split roles for development and production separation. 3) Implement segregation-of-duties (SoD) reviews and reduce users authorized to change/reset passwords.\n\n- Use PFCG to adjust roles and SUIM to verify users/roles impacted.",
      "Preventative Action": "Enforce periodic authorization reviews and approval-based role changes; build SoD checks into change management."
    },
    {
      "Issue ID": "KF-05",
      "Area": "Configuration & House-keeping",
      "Severity": "medium",
      "Source": "Service Data Quality and Service Readiness -> Sending EarlyWatch Alert of BIP to SAP Backbone",
      "Finding": "EWA data is not sent to SAP Support Backbone (Solution Manager SMP 'no' for sending EWA data).",
      "Impact": "SAP cannot access EWA workspace details; delays in remote SAP support and application of SAP-recommended fixes.",
      "Business impact": "Reduced proactive support and delayed incident handling; longer MTTR for upcoming issues.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "Project / Change Management",
      "Action": "1) Enable sending EarlyWatch Alert (EWA) data to SAP Support Backbone via Solution Manager SMP (configure HTTPS destinations and verify SM59/destinations). 2) Complete EWA connectivity checklist from the report: create HTTPS connections and technical communication user as instructed in the Service Readiness section.\n\n- Verify EWA transfer and test SAP for Me visibility.",
      "Preventative Action": "Add EWA connection verification to quarterly BASIS health checks to ensure remote support telemetry remains active."
    },
    {
      "Issue ID": "KF-06",
      "Area": "Performance & Workload",
      "Severity": "high",
      "Source": "BW Checks for BIP -> BW - KPIs; Workload Overview; Top InfoProviders",
      "Finding": "BW / InfoProviders: 30 InfoProviders with >=10000 requests; top InfoProvider ZIPVOP02 shows 239,880 requests; several InfoProviders causing high DB/OLAP load and planning functions with long PF logic times.",
      "Impact": "High and concentrated workload leads to long query runtimes and HANA resource pressure, contributing to heavy TREX DB calls and CPU spikes.",
      "Business impact": "User experience degradation, delayed reporting, business process slowdowns; potential SLA violations.",
      "Estimated Effort": {
        "analysis": "high",
        "implementation": "high"
      },
      "Responsible Area": "Application Development",
      "Action": "1) Execute BW performance triage: identify top queries/InfoProviders (ZIPVOP02, ZIPVLP01, ZSDRSC04 etc.) and apply targeted optimizations: OLAP cache tuning, aggregates, indices, or logical partitioning (SPO). 2) Re-design heavy queries and move frequently-used aggregates to database-friendly structures; split large InfoCubes where relevant. 3) Reschedule heavy loads/process chains to off-peak windows; implement throttling or staging where possible.\n\n- Use RTCCTOOL/ST-PI updated code per SAP Note 3482369 to collect accurate metrics and re-run analysis.",
      "Preventative Action": "Establish BW performance governance: monthly review of top InfoProviders, enforce query design best practices and OLAP cache policy; train authors on Analysis for Office migration to reduce legacy BEx load."
    },
    {
      "Issue ID": "KF-07",
      "Area": "SAP HANA",
      "Severity": "medium",
      "Source": "SAP HANA Stability and Alerts -> Alerts table (IDs 65 and 62)",
      "Finding": "SAP HANA alerts flagged: long-running log backup (Alert 65) and user password expiration checks flagged (Alert 62).",
      "Impact": "Operational instability from slow log backups; password expirations/blocking may cause unplanned service interruptions for technical users.",
      "Business impact": "Potential restore/recovery delays; application outages when technical users get locked.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "Database Administration",
      "Action": "1) Investigate and resolve long-running log backup issues (alert 65) — check backup target performance and parallelism; ensure log backup window completes within expected time. 2) For alert 62, disable password lifetime for technical users or migrate technical users to non-expiring accounts as per SAP Note 2082406.\n\n- Validate backup retention and execution times; adjust backup tool concurrency if needed.",
      "Preventative Action": "Monitor log backup durations weekly and include technical user password lifetime exceptions in password policy documentation."
    },
    {
      "Issue ID": "KF-08",
      "Area": "SAP HANA",
      "Severity": "medium",
      "Source": "SAP HANA Database Configuration -> Parameter Recommendation; Parameters deviating from default",
      "Finding": "SAP HANA parameters deviate from recommended values (examples: gc thresholds, mergedog settings, itab_initial_buffer_size, thread stack sizes, suspended_cursor_lifetime not in recommended range).",
      "Impact": "Suboptimal memory management and merge/merge-decision behavior can cause delayed merges, higher memory footprint, or inefficient merges.",
      "Business impact": "Performance instability, unpredictable merge behavior and possible increased memory pressure during merges.",
      "Estimated Effort": {
        "analysis": "medium",
        "implementation": "medium"
      },
      "Responsible Area": "Database Administration",
      "Action": "1) Review and align HANA global.ini and indexserver.ini parameters against SAP Note 2222250 and the EWA recommendations (gc thresholds, mergedog settings, worker/stack sizes, suspended_cursor_lifetime). 2) Implement recommended values (e.g., smart_merge_decision_func, max_cpuload_for_merge, parallel_merge_threads) in a controlled manner, test on non-prod tenant.\n\n- Re-run EWA checks after changes to verify impact.",
      "Preventative Action": "Include parameter baseline and change control in the HANA maintenance process; document parameter rationales."
    },
    {
      "Issue ID": "KF-09",
      "Area": "Configuration & House-keeping",
      "Severity": "medium",
      "Source": "Hardware Capacity -> Enhanced Hardware Monitoring in Cloud Environments",
      "Finding": "Enhanced hardware monitoring in cloud IaaS (Azure) not active for application hosts azsabipaas01 and azsabippas; enhanced monitoring recommended (SAP Note 2191498 / 2469354).",
      "Impact": "Reduced visibility of underlying IaaS performance impact; inability to correlate SAP-level events to IaaS metrics.",
      "Business impact": "Slower root-cause analysis for performance incidents; possible missed IaaS-level resource bottlenecks.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "Infrastructure / Hardware Team",
      "Action": "1) Enable enhanced monitoring for Azure virtual hosts per SAP Note 2191498 / 2469354 to collect IaaS metrics (IaaS-specific monitors). 2) Validate that the SAP Host Agent and embedded monitors can report required metrics to Solution Manager.\n\n- Coordinate with cloud provider to enable the required guest metrics and permissions.",
      "Preventative Action": "Ensure enhanced monitoring is part of the infrastructure provisioning standard for SAP virtual machines."
    },
    {
      "Issue ID": "KF-10",
      "Area": "Upgrade / Patch Management",
      "Severity": "high",
      "Source": "Service Preparation -> Service Preparation Check (RTCCTOOL); Software Configuration -> Support Packages",
      "Finding": "ST-PI / ST-A/PI and other support packages are behind latest available patches (ST-PI 740 at SP30 vs recommended SP32, multiple SAP_BASIS/SAP_ABA SAPK levels behind).",
      "Impact": "Missing functional and security fixes; incompatibilities in analysis tools; reduced supportability.",
      "Business impact": "Increased vulnerability surface and potential functional regressions; additional work to catch up multiple stack levels.",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "medium"
      },
      "Responsible Area": "SAP Basis Team",
      "Action": "1) Implement required ST-PI and ST-A/PI add-on updates (ST-PI 740 -> recommended SP32) using SPAM/SAINT and follow the RTCCTOOL recommendations (SAP note 3482369). 2) Schedule full support package stack maintenance for ABAP components shown outdated (SAP_BASIS, SAP_ABA, SAP_BW, etc.).\n\n- Validate with system owners and schedule remediation windows.",
      "Preventative Action": "Maintain a 12-month SP update cadence and validate System Recommendations application monthly for security notes."
    },
    {
      "Issue ID": "KF-11",
      "Area": "Performance & Workload",
      "Severity": "high",
      "Source": "SAP HANA SQL Statements in HAP -> Top Statements (Thread Samples / Total Memory / Elapsed Time)",
      "Finding": "Several heavy SQL/TREX calls dominate CPU (CALL SYS.TREXviaDBSL and large BW load INSERT statements) — single statements consume high memory and CPU during peak hours.",
      "Impact": "Severe CPU spikes and memory usage leading to reduced responsiveness for other workloads during peaks.",
      "Business impact": "Operational slowdowns for reporting, planning, and transactional processing; risk of saturation during business-critical hours.",
      "Estimated Effort": {
        "analysis": "high",
        "implementation": "high"
      },
      "Responsible Area": "Database Administration",
      "Action": "1) Investigate top HANA SQL/TREX statements (CALL SYS.TREXviaDBSL) and long-running INSERTs from DTP loads. 2) For TREX calls, review BIA design, rework BIA indexes or adjust OLAP cache/partitioning. 3) Optimize process chains and DTP settings to reduce parallel heavy queries; consider splitting large DTPs into smaller packages and reduce data package count per request.\n\n- Use SQL Plan Cache and expensive statement trace details to identify exact query patterns to rewrite or parameterize.",
      "Preventative Action": "Schedule heavy loads during off-peak, apply query-level workload management in HANA and restrict statement memory/thread limits for non-critical workloads."
    },
    {
      "Issue ID": "KF-12",
      "Area": "SAP HANA",
      "Severity": "medium",
      "Source": "SAP HANA Database HAP -> Global Consistency Check Run",
      "Finding": "Global consistency check not run; only lightweight/partial consistency checks scheduled via statistics server.",
      "Impact": "Potential undetected table/catalog inconsistencies; risk during recovery or upgrades.",
      "Business impact": "Risk of data integrity issues not surfaced before a critical operation (upgrade/restore).",
      "Estimated Effort": {
        "analysis": "low",
        "implementation": "low"
      },
      "Responsible Area": "Database Administration",
      "Action": "1) Configure and run the full table-level global consistency check (CHECK_TABLE_CONSISTENCY) per SAP guidance; schedule during low-load windows. 2) Ensure statistics server runs the full checks and monitor completion percentage; resolve any not-verified tables.\n\n- Follow SAP Notes 2116157 and HANA Admin Guide for recommended scheduling.",
      "Preventative Action": "Add consistency check status to system health dashboards and alert if incomplete for >7 days."
    }
  ]
}
```


---

<div style='page-break-before: always;'></div>

## Key Performance Indicators
| Area | Indicator | Value | Trend |
| ---|---|---|--- |
| System Performance | Active Users (>400 steps) | 41 | → |
| System Performance | Avg. Availability per Week | 100 % | ↘ |
| System Performance | Avg. Response Time in Dialog Task | 947 ms | ↘ |
| System Performance | Max. Dialog Steps per Hour | 179 | ↘ |
| System Performance | Avg. Response Time at Peak Dialog Hour | 806 ms | ↘ |
| System Performance | Avg. Response Time in RFC Task | 4317 ms | ↘ |
| System Performance | Max. Number of RFCs per Hour | 5876 | → |
| System Performance | Avg. RFC Response Time at Peak Hour | 582 ms | ↘ |
| Hardware Capacity | Max. CPU Utilization on DB Server | 31 % | → |
| Hardware Capacity | Max. CPU Utilization on Appl. Server | 31 % | ↗ |
| Database Performance | Avg. DB Request Time in Dialog Task | 170 ms | ↘ |
| Database Performance | Avg. DB Request Time for RFC | 255 ms | ↘ |
| Database Performance | Avg. DB Request Time in Update Task | 9 ms | ↘ |
| Database Space Management | DB Size | 1633.80 GB | → |
| Database Space Management | DB Growth Last Month | 22.81 GB | ↗ |

---

<div style='page-break-before: always;'></div>

## Capacity Outlook
- **Database Growth:** DB Size 1,633.80 GB; DB Growth Last Month 22.81 GB (reported) — extrapolated annual growth ~273.7 GB/year based on recent month.
- **CPU Utilization:** Max CPU Utilization on DB Server 31%; App servers max 31% — no immediate CPU capacity shortfall but spikes during TREX/SQL heavy windows observed (peak CPU events correlated with heavy statements).
- **Memory Utilization:** HANA instance memory usage weekly average ~1,630 GB of global_allocation_limit 3,771 GB (~43%). Indexserver effective allocation ~3,713 GB; memory headroom exists but single-statements have consumed up to ~204 GB in trace — watch single-statement memory consumption.
- **Capacity Summary:** Stable day-to-day capacity with sufficient baseline CPU/memory headroom. Key risk: workload concentration (BW queries, TREX calls, large DTPs) causes transient peaks and large single-statement memory allocations; upgrade and query tuning recommended to avoid near-term capacity exhaustion.

---
