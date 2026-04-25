# SAP EWA Comprehensive Threshold Reference

This document contains the complete threshold tables for every domain covered
in an SAP EarlyWatch Alert report. The main SKILL.md has the most common
thresholds — this file is the exhaustive reference.

## Table of Contents

1. [System & Kernel](#system--kernel)
2. [Hardware & Sizing](#hardware--sizing)
3. [SAP Memory Management](#sap-memory-management)
4. [ABAP Workload Performance](#abap-workload-performance)
5. [Database Performance — General](#database-performance--general)
6. [Database Performance — HANA Specific](#database-performance--hana-specific)
7. [Database Performance — Oracle Specific](#database-performance--oracle-specific)
8. [Database Performance — SQL Server Specific](#database-performance--sql-server-specific)
9. [Batch Processing](#batch-processing)
10. [Security & Compliance](#security--compliance)
11. [Spool & Output Management](#spool--output-management)
12. [Transport & Change Management](#transport--change-management)
13. [System Logs & ABAP Dumps](#system-logs--abap-dumps)
14. [Internet Communication Manager (ICM)](#internet-communication-manager-icm)
15. [Enqueue & Lock Management](#enqueue--lock-management)

---

## System & Kernel

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Kernel patch level age | < 6 months | 6–12 months | > 12 months | SM51, SMSY | Kernel patches include security fixes and performance improvements |
| Support package age | < 12 months | 12–24 months | > 24 months | SPAM | Old SPs may miss bug fixes and regulatory updates |
| SAP_BASIS release | Current - 1 | Current - 2 | Current - 3+ | SE01 | End-of-maintenance risk |
| Number of instances | — | — | — | SM51 | Context only — no inherent threshold |
| OS patch level | Current quarter | Previous quarter | > 2 quarters behind | ST06 | OS vulnerabilities compound with SAP exposure |

---

## Hardware & Sizing

### CPU

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Average CPU utilization | < 60% | 60–80% | > 80% | ST06, OS07 | Average masks spikes — check peaks too |
| Peak CPU utilization | < 70% | 70–85% | > 85% | ST06 | Above 85% causes scheduling delays |
| CPU steal time (virtual) | < 2% | 2–10% | > 10% | ST06 | Hypervisor contention — not fixable at OS level |
| Number of CPUs vs. SAPS | Within sizing | 10–20% over | > 20% over | — | Compare against SAP benchmark (SAPS) |
| CPU ready time (VMware) | < 5% | 5–15% | > 15% | — | VM waiting for physical CPU |

### Physical Memory

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Physical memory utilization | < 80% | 80–92% | > 92% | ST06 | Leave headroom for OS caches |
| Swap space utilization | < 5% | 5–20% | > 20% | ST06 | Active swapping = severe performance hit |
| Swap-in/out rate | < 100 pages/s | 100–1000 | > 1000 | ST06 | Sustained swapping indicates real memory pressure |
| Page faults (major) | < 10/s | 10–100/s | > 100/s | ST06 | Major faults = disk I/O for memory pages |

### Storage I/O

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Disk read latency | < 5ms | 5–15ms | > 15ms | ST06 | Enterprise storage should be < 5ms |
| Disk write latency | < 5ms | 5–15ms | > 15ms | ST06 | Write latency impacts DB commit time |
| I/O throughput utilization | < 60% | 60–80% | > 80% | ST06 | Headroom for peak loads |
| Disk queue depth | < 2 | 2–8 | > 8 | ST06 | High queue = I/O saturation |

---

## SAP Memory Management

### Extended Memory (EM)

| Metric | Healthy | Warning | Critical | Transaction | Parameter |
|--------|---------|---------|----------|-------------|-----------|
| EM utilization | < 80% | 80–95% | > 95% | ST02 | em/initial_size_MB |
| EM attached (per user) | < em/max_size_MB | Close to limit | At limit | AL05, SM04 | em/max_size_MB |
| EM free | > 20% | 5–20% | < 5% | ST02 | — |

### Roll & Page Memory

| Metric | Healthy | Warning | Critical | Transaction | Parameter |
|--------|---------|---------|----------|-------------|-----------|
| Roll area utilization | < 70% | 70–90% | > 90% | ST02 | ztta/roll_area |
| Page area utilization | < 70% | 70–90% | > 90% | ST02 | ztta/page_area |
| Roll file usage (on disk) | Minimal | Moderate | Heavy | ST02 | — |

### Heap Memory

| Metric | Healthy | Warning | Critical | Transaction | Parameter |
|--------|---------|---------|----------|-------------|-----------|
| Heap memory allocation frequency | Rare | Occasional | Frequent | ST02 | abap/heap_area_total |
| Heap memory per WP | < abap/heap_area_dia | — | At limit | ST02 | abap/heap_area_dia |
| Private mode work processes | 0–1 at any time | 2–3 | > 3 | SM50, SM66 | — |

### Buffer Performance

| Buffer | Healthy Hit Ratio | Warning | Critical | Transaction |
|--------|-------------------|---------|----------|-------------|
| Program buffer (PXA) | > 98% | 95–98% | < 95% | ST02 |
| Table buffer (generic) | > 98% | 95–98% | < 95% | ST02 |
| Table buffer (single record) | > 95% | 90–95% | < 90% | ST02 |
| CUA buffer | > 98% | 95–98% | < 95% | ST02 |
| Screen buffer | > 98% | 95–98% | < 95% | ST02 |
| Calendar buffer | > 95% | 90–95% | < 90% | ST02 |
| Nametab buffer | > 98% | 95–98% | < 95% | ST02 |
| Short nametab buffer | > 98% | 95–98% | < 95% | ST02 |

### Buffer Swaps

| Metric | Healthy | Warning | Critical | Notes |
|--------|---------|---------|----------|-------|
| Buffer swaps (any buffer) | 0 | < 100/day | > 100/day | Swaps indicate buffer is too small |
| Directory swaps | 0 | Any | — | Directory full = can't cache new objects |
| Data swaps | 0 | < 50/day | > 50/day | Data area full = oldest entries evicted |

---

## ABAP Workload Performance

### Dialog Processing

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Avg dialog response time | < 1.0s | 1.0–2.0s | > 2.0s | ST03N | End-to-end including wait time |
| Avg DB request time / dialog step | < 200ms | 200–400ms | > 400ms | ST03N | DB is usually the largest contributor |
| Avg CPU time / dialog step | < 150ms | 150–300ms | > 300ms | ST03N | High = expensive custom ABAP |
| Avg roll wait time | < 200ms | 200–500ms | > 500ms | ST03N | RFC wait or enqueue wait |
| Avg load+gen time | < 50ms | 50–100ms | > 100ms | ST03N | Buffer misses causing reloads |
| GUI time / RFC time | < 300ms | 300–800ms | > 800ms | ST03N | Network or frontend bottleneck |
| Dialog steps per hour | Baseline | ±20% | ±50% | ST03N | Major deviations indicate changed usage |

### Work Process Utilization

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Dialog WP utilization | < 60% | 60–80% | > 80% | SM50, SM66 | Leave headroom for peak bursts |
| Dialog WP in PRIV mode | 0 | 1–2 | > 2 | SM66 | PRIV = process locked to one user |
| Update WP utilization | < 50% | 50–70% | > 70% | SM66 | Update queue backs up fast |
| Update errors | 0 | Any | — | SM13 | Every update error = lost business data |

### Top Transactions

| Factor | Healthy | Warning | Critical | Notes |
|--------|---------|---------|----------|-------|
| Single transaction % of total time | < 15% | 15–30% | > 30% | One transaction dominating = optimization target |
| Custom code (Z/Y) response time | < 1.5s | 1.5–3.0s | > 3.0s | Custom code is the primary tuning opportunity |
| RFC calls per dialog step | < 5 | 5–20 | > 20 | Chatty RFCs degrade response time |

---

## Database Performance — General

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Data buffer cache hit ratio | > 98% | 95–98% | < 95% | ST04 | Below 95% = excessive disk reads |
| Log buffer wait ratio | < 1% | 1–5% | > 5% | ST04 | Writes waiting for log flush |
| DB space utilization | < 75% | 75–85% | > 85% | DB02 | Plan for growth |
| DB growth rate | < 5%/month | 5–10%/month | > 10%/month | DB02 | Project months to full |
| Expensive SQL statements | 0–2 | 3–5 | > 5 | ST04, DBACOCKPIT | Statements taking > 20% of DB time |
| Full table scans on large tables | 0 | 1–3 | > 3 | ST05 | Missing index or poor query design |
| Deadlocks | 0 | < 5/day | > 5/day | ST04 | Application design issue |

---

## Database Performance — HANA Specific

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Column store memory usage | < 80% | 80–90% | > 90% | HANA Studio/DBACOCKPIT | Primary HANA resource |
| Delta merge frequency | Regular | Irregular | Stopped | DBACOCKPIT | Delta merge is essential for CS performance |
| Row store size | < 10% of total | 10–25% | > 25% | DBACOCKPIT | Row store should be minimal in HANA |
| Disk usage (log volume) | < 70% | 70–85% | > 85% | DB02 | Even HANA needs disk for persistence |
| Backup age | < 24h | 24–72h | > 72h | DBACOCKPIT | Critical for recovery |
| Alert count (HANA alerts) | 0 | 1–5 | > 5 | DBACOCKPIT | HANA's own alerting system |
| Memory allocation limit utilization | < 85% | 85–95% | > 95% | DBACOCKPIT | global_allocation_limit |

---

## Database Performance — Oracle Specific

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Library cache hit ratio | > 99% | 95–99% | < 95% | ST04 | Hard parses are expensive |
| Dictionary cache hit ratio | > 95% | 90–95% | < 90% | ST04 | Metadata lookup misses |
| Redo log switches per hour | < 6 | 6–12 | > 12 | ST04 | Too frequent = redo logs too small |
| Tablespace free % | > 20% | 10–20% | < 10% | DB02 | Per-tablespace monitoring |
| Archive log destination utilization | < 70% | 70–85% | > 85% | DB12 | Full = database stops |

---

## Database Performance — SQL Server Specific

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Plan cache hit ratio | > 95% | 90–95% | < 90% | ST04 | Plan recompilation overhead |
| Page life expectancy | > 300s | 100–300s | < 100s | ST04 | Time a page stays in buffer pool |
| Latch waits | Low | Moderate | High | ST04 | Internal contention |
| Auto-growth events (recent) | 0 | 1–5 | > 5 | DB02 | Each auto-grow = performance pause |
| TempDB contention | Low | Moderate | High | ST04 | Can bottleneck sort/hash operations |

---

## Batch Processing

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Background WP utilization | < 70% | 70–90% | > 90% | SM50, SM66 | Near-saturation blocks new jobs |
| Failed jobs (% of total) | < 1% | 1–5% | > 5% | SM37 | Failed = failed business process |
| Cancelled jobs | 0 | 1–3/day | > 3/day | SM37 | Cancellations need investigation |
| Long-running jobs (> 1hr) | 0 | 1–3 | > 3 | SM37 | Review if intentional (data loads) or bugs |
| Job scheduling conflicts | 0 | Any | — | SM36, SM61 | Overlapping exclusive jobs |
| Average job delay | < 5 min | 5–30 min | > 30 min | SM37 | Time between scheduled and actual start |

---

## Security & Compliance

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Users with SAP_ALL (prod) | 0 | 1–3 | > 3 | SUIM | Full bypass of authorization |
| Users with SAP_NEW | 0 | Any | — | SUIM | Temporary profile — should be removed |
| Default passwords unchanged | 0 | — | Any | RSUSR003 | Always at least High severity |
| Inactive users (> 90 days) | < 5% | 5–15% | > 15% | SUIM | Security hygiene — orphaned accounts |
| RFC destinations without secure auth | 0 | — | Any | SM59 | Direct attack vector |
| System users with dialog login | 0 | Any | — | SU01 | System users should not have dialog access |
| Password policy — min length | ≥ 8 | 6–7 | < 6 | RZ10 | login/min_password_lng |
| Password policy — expiration | ≤ 90 days | 91–180 | > 180 or none | RZ10 | login/password_expiration_time |
| Failed logon attempts before lock | ≤ 5 | 6–10 | > 10 or disabled | RZ10 | login/fails_to_session_end |
| Gateway security config | Configured | Partial | Missing | SMGW | gw/sec_info, gw/reg_info |
| ICF service exposure | Minimal | Moderate | Excessive | SICF | Deactivate unused HTTP services |

---

## Spool & Output Management

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| TemSe objects count | < 10,000 | 10K–50K | > 50K | SP01 | Old spool requests consume space |
| TemSe objects age | < 7 days | 7–30 days | > 30 days | SP01 | Auto-cleanup should be configured |
| Spool growth trend | Stable | Growing | Rapidly growing | SP01 | Indicates misconfigured output |
| Failed print requests | < 1% | 1–5% | > 5% | SP01 | Printer config or connectivity |

---

## Transport & Change Management

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Import errors | 0 | 1–3 | > 3 | STMS | Failed imports = inconsistent system |
| Import queue age | < 7 days | 7–30 days | > 30 days | STMS | Old queued transports indicate process issues |
| Objects in repair state | 0 | 1–5 | > 5 | SE01 | Repairs break the transport model |
| Cross-client transports pending | — | Any in prod | — | STMS | Cross-client changes need extra review |

---

## System Logs & ABAP Dumps

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Short dumps per day | < 10 | 10–50 | > 50 | ST22 | Systematic dumps need root cause analysis |
| Unique dump names (trending) | Stable | Increasing | Rapidly increasing | ST22 | New dump types = new problems |
| Security-related log events | 0 | Any | — | SM21 | Failed logons, authorization failures |
| System restart count (30 days) | 0–1 | 2–3 | > 3 | SM21 | Unexpected restarts = stability issue |
| W- and E-type messages in syslog | Few | Moderate | Many | SM21 | Warning and error messages |

---

## Internet Communication Manager (ICM)

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| ICM thread utilization | < 60% | 60–80% | > 80% | SMICM | HTTP thread exhaustion |
| ICM connection errors | 0 | < 10/day | > 10/day | SMICM | Connectivity or certificate issues |
| HTTP response time (avg) | < 500ms | 500–1500ms | > 1500ms | SMICM | Web/Fiori performance |

---

## Enqueue & Lock Management

| Metric | Healthy | Warning | Critical | Transaction | Notes |
|--------|---------|---------|----------|-------------|-------|
| Enqueue rejects | 0 | < 10/day | > 10/day | SM12, ST04 | Lock table full or contention |
| Lock wait time | < 100ms | 100–500ms | > 500ms | SM12 | Long waits indicate blocking |
| Enqueue table utilization | < 50% | 50–75% | > 75% | SM12 | enque/table_size |
| Deadlock count | 0 | < 5/day | > 5/day | SM12 | Application design issue |
