# SAP EWA Remediation Patterns

Detailed remediation playbooks for common EWA findings. Each pattern includes
the exact steps, parameters, transactions, and effort estimates an SAP Basis
administrator needs to resolve the issue.

Read the relevant section when generating remediation plans for findings.

## Table of Contents

1. [Memory & Buffer Remediation](#memory--buffer-remediation)
2. [Performance & Workload Remediation](#performance--workload-remediation)
3. [Database Remediation](#database-remediation)
4. [Batch Processing Remediation](#batch-processing-remediation)
5. [Security Remediation](#security-remediation)
6. [System Maintenance Remediation](#system-maintenance-remediation)
7. [Storage & Housekeeping Remediation](#storage--housekeeping-remediation)
8. [Effort Estimation Guide](#effort-estimation-guide)

---

## Memory & Buffer Remediation

### REM-MEM-01: Extended Memory Exhaustion

**Symptoms**: EM utilization > 95%, users getting "storage parameters exhausted"
errors, work processes in PRIV mode.

**Root Cause**: Either too many concurrent users for the configured EM, or
individual sessions consuming excessive memory (large ALV reports, complex
SELECT statements materializing large result sets).

**Remediation Steps**:

1. **Immediate** — Check which users/programs are consuming the most EM:
   - Transaction `AL05` → View current resource consumption per user
   - Transaction `SM04` → Check user sessions and memory per session
   - Identify the top consumers — if one program uses 500MB+, investigate that
     program specifically

2. **Short-term** — Increase extended memory allocation:
   - Transaction `RZ10` → Edit instance profile
   - Parameter: `em/initial_size_MB` — increase by 50% (e.g., 16384 → 24576)
   - Parameter: `em/max_size_MB` — per-process limit, increase proportionally
   - Requires instance restart

3. **Medium-term** — Prevent recurrence:
   - Parameter: `ztta/roll_area` — increase if roll area is also pressured
   - Review custom reports (Z/Y programs) for excessive memory usage via ST05/SAT
   - Consider implementing memory quotas per user group

**Effort**: Medium (parameter change = Low, but restart coordination = Medium)
**Priority**: Immediate if users are affected, Short-term if only trending

---

### REM-MEM-02: Buffer Quality Degradation

**Symptoms**: Hit ratio < 95% on any SAP buffer, swap/eviction counts increasing.

**Root Cause**: Buffer is too small for the working set. As the system grows
(more programs, tables, users), buffers that were once sized correctly become
insufficient.

**Remediation Steps**:

1. **Diagnose which buffer is affected** via `ST02`:
   - Check "Swaps" column — if > 0, the buffer is too small
   - Check "Directory" vs "Data" — tells you which dimension is too small
   - Check "Free" percentage — if < 10%, buffer needs expansion

2. **Increase the specific buffer** (via `RZ10`):

   | Buffer | Parameter | Typical Increase |
   |--------|-----------|-----------------|
   | Program (PXA) | abap/buffersize | +50% |
   | Generic table | zcsa/table_buffer_area | +50% |
   | Single record table | rtbb/buffer_length | +50% |
   | CUA | rsdb/cua/buffersize | +25% |
   | Nametab | rsdb/ntab/buffersize | +50% |
   | Short nametab | rsdb/ntab/sntab_buffersize | +50% |
   | Screen | rsdb/scr/buffersize | +25% |

3. **Validate after restart**: Check ST02 again after 24 hours of normal
   operation — hit ratio should return to > 98%

**Effort**: Low (parameter change + planned restart)
**Priority**: Short-term

---

### REM-MEM-03: Heap Memory Overuse

**Symptoms**: Frequent heap allocations visible in ST02, work processes going
to PRIV mode, "cannot obtain enough memory" errors.

**Root Cause**: Programs requesting memory beyond the extended memory limit
fall back to heap. This is SAP's last-resort memory allocation and is per-process
(not shared). Work processes in heap mode go to PRIV and cannot serve other users
until the transaction completes.

**Remediation Steps**:

1. **Identify offending programs**: `SM50` → look for processes in PRIV mode,
   note the program name and transaction code
2. **Review the programs**: Common culprits are:
   - Large internal table operations without pagination
   - SELECT * FROM large tables without WHERE clause
   - ALV reports materializing millions of rows
3. **Adjust memory parameters** (if programs are legitimate):
   - `abap/heap_area_total` — total heap per instance
   - `abap/heap_area_dia` — max heap per dialog WP
   - `abap/heap_area_nondia` — max heap per batch/update WP
4. **Code-level fix** (preferred long-term):
   - Add row limits to reports
   - Use cursor-based processing instead of bulk SELECT
   - Implement pagination for ALV output

**Effort**: High (requires code review and potentially ABAP changes)
**Priority**: Short-term

---

## Performance & Workload Remediation

### REM-PERF-01: High Dialog Response Time

**Symptoms**: Average dialog response time > 1.0s, user complaints about system
speed, high wait times in SM66.

**Root Cause**: Dialog response time is the sum of CPU time + DB time + roll wait
+ load/gen time + GUI time. Identify which component dominates:

**Remediation Steps**:

1. **Decompose the response time** via `ST03N`:
   - Navigate to Workload Analysis → select time period
   - Read the "Response Time" breakdown:
     - **CPU time dominant (> 40%)**: Custom ABAP code inefficiency
     - **DB time dominant (> 40%)**: Database queries need tuning
     - **Roll wait dominant**: RFC or enqueue contention
     - **Load/gen dominant**: Buffer misses (see REM-MEM-02)
     - **GUI time dominant**: Network or frontend issue

2. **For high CPU time**:
   - `ST03N` → Top Transactions → identify Z/Y transactions with high CPU
   - `SAT` (runtime analysis) on the specific transaction
   - Look for nested loops, unnecessary table reads, redundant calculations
   - Engage ABAP developers for optimization

3. **For high DB time**:
   - See REM-DB-01 (Database Query Optimization)

4. **For high roll wait time**:
   - Check RFC destinations: `SM59` → test connections, check response times
   - Check enqueue wait: `SM12` → look for long-held locks
   - Check update queue: `SM13` → ensure no update backlog

5. **For high GUI/network time**:
   - Check network latency between SAP server and client network
   - Consider SAP GUI optimizations or Fiori migration for WAN users

**Effort**: Medium to High (depends on dominant component)
**Priority**: Immediate if > 2s, Short-term if 1–2s

---

### REM-PERF-02: Work Process Saturation

**Symptoms**: WP utilization > 80%, users seeing "no dialog work process available"
errors, SM50 shows all WPs busy.

**Root Cause**: Either too few work processes for the user base, or long-running
transactions monopolizing work processes.

**Remediation Steps**:

1. **Check for stuck/long-running processes**: `SM50` / `SM66`
   - Note any process running > 5 minutes in dialog mode
   - PRIV mode processes reduce available WP count

2. **Short-term — Increase work process count**:
   - `RZ10` → `rdisp/wp_no_dia` (dialog)
   - `RZ10` → `rdisp/wp_no_btc` (background)
   - Rule of thumb: 1 dialog WP per 10-15 concurrent users
   - Remember: total WPs per instance should not exceed 2× CPU cores

3. **Medium-term — Add application server instances**:
   - Distribute load via logon groups (`SMLG`)
   - Better than overloading a single instance

4. **Optimize — Reduce WP consumption**:
   - Move heavy dialog transactions to batch (`SM36`)
   - Configure operation modes for business hours vs. batch windows (`RZ04`)

**Effort**: Medium (parameter change is easy, but capacity planning needed)
**Priority**: Immediate if users are locked out

---

### REM-PERF-03: Custom Code Performance

**Symptoms**: Z/Y transactions appearing in ST03N top list, high CPU time in
custom code, slow response times for specific custom transactions.

**Remediation Steps**:

1. **Identify the problem transactions**: `ST03N` → Top Transactions
   - Sort by total response time
   - Filter for Z* / Y* transactions
   - Note the transaction code, program name, and average response time

2. **Profile the code**: `SAT` (runtime analysis)
   - Execute the transaction under SAT trace
   - Identify the top time consumers (usually SELECT statements or loops)

3. **Common custom code issues and fixes**:

   | Issue | Fix |
   |-------|-----|
   | SELECT * FROM large_table | Add WHERE clause, specify needed columns |
   | SELECT in a loop (N+1 problem) | Use FOR ALL ENTRIES or JOIN |
   | Nested LOOP AT with large tables | Use SORTED tables or HASHED tables |
   | Unnecessary COMMIT WORK in loops | Move COMMIT outside the loop |
   | Missing secondary index | Create index via SE11 |
   | Full table scans | Add appropriate WHERE clause |

4. **Engage ABAP development team** with:
   - SAT trace results showing the hotspot
   - ST05 SQL trace showing expensive queries
   - Suggested optimization approach

**Effort**: High (requires ABAP development)
**Priority**: Medium-term (unless causing Critical performance issues)

---

## Database Remediation

### REM-DB-01: Database Query Optimization

**Symptoms**: High DB request time in ST03N, expensive SQL statements in ST04,
full table scans on large tables.

**Remediation Steps**:

1. **Identify expensive SQL**: `DBACOCKPIT` or `ST04`
   - Top SQL by elapsed time
   - Top SQL by executions
   - Any single SQL consuming > 20% of total DB time

2. **Analyze the SQL**:
   - `ST05` → SQL Trace → execute the transaction → analyze the trace
   - Look for: missing WHERE clause, missing index, full table scans
   - Check explain plan: `SE11` → Utilities → DB Analysis

3. **Create missing indexes**:
   - `SE11` → Table → Indexes → Create
   - Only for custom tables or as per SAP Note recommendations
   - For SAP standard tables: check SAP Notes first — SAP may already have
     an index correction

4. **Optimize via database tools**:
   - HANA: `SQL Plan Cache` analysis in HANA Studio
   - Oracle: `AWR` reports via DBACOCKPIT
   - SQL Server: `Query Store` analysis

5. **Engage development** for code-level fixes if the SQL is from custom code

**Effort**: Medium (index creation = Low, code fix = High)
**Priority**: Short-term

---

### REM-DB-02: Database Space Management

**Symptoms**: DB space utilization > 85%, rapid growth trajectory, tablespace
alerts.

**Remediation Steps**:

1. **Identify space consumers**: `DB02`
   - Top 20 tables by size
   - Growth trend over last 3–6 months
   - Tables with excessive fragmentation

2. **Implement data archiving**:
   - `SARA` — Archiving management
   - Start with the largest tables: change documents (CDHDR/CDPOS),
     application logs (BAL*), workflow (SWW*), spool (TSP*)
   - Create archiving variants and test in non-production first

3. **Housekeeping for known space consumers**:

   | Area | Cleanup Transaction | Target Tables |
   |------|-------------------|---------------|
   | Spool | RSPO_TEMSE_DELETE, SP12 | TST01, TST03, TSP01 |
   | Application logs | SLG2 | BALHDR, BALDAT |
   | Change documents | Archive via SARA | CDHDR, CDPOS |
   | Job logs | SM37 → delete old | TBTCP, TBTCO |
   | Workflow | SWI2_FREQ | SWWWIHEAD, SWW* |
   | Temporary tables | Cleanup reports | Various temp tables |

4. **Extend storage** (if archiving alone is insufficient):
   - Add datafiles/tablespace extensions
   - Monitor with DB02 alerts

**Effort**: Medium to High (archiving setup requires functional team input)
**Priority**: Short-term if > 85%, Immediate if > 90%

---

### REM-DB-03: Database Buffer/Cache Tuning

**Symptoms**: Buffer cache hit ratio < 95%, excessive physical reads, high I/O
wait times.

**Remediation Steps**:

1. **Check current buffer allocation** via `ST04` or `DBACOCKPIT`

2. **Increase buffer pool** (database-specific):

   | Database | Parameter | How to Change |
   |----------|-----------|---------------|
   | HANA | global_allocation_limit | HANA Studio → Configuration |
   | Oracle | db_cache_size, shared_pool_size | init.ora / spfile |
   | SQL Server | max server memory | SSMS → Server Properties |
   | DB2 | BUFFERPOOL sizes | db2 ALTER BUFFERPOOL |

3. **Monitor after change**: Wait 24 hours, re-check hit ratios in ST04

**Effort**: Low (parameter change, DB-level — no SAP restart needed for most DBs)
**Priority**: Short-term

---

## Batch Processing Remediation

### REM-BATCH-01: Failed Batch Jobs

**Symptoms**: Job failure rate > 1%, specific jobs failing repeatedly,
dependent job chains broken.

**Remediation Steps**:

1. **Identify failed jobs**: `SM37` → filter for "Cancelled" status
   - Note job name, scheduled user, step program
   - Read the job log for the error message

2. **Common failure causes and fixes**:

   | Error Type | Typical Cause | Fix |
   |-----------|--------------|-----|
   | Authorization error | Step user lacks permissions | Fix authorization via SU01/PFCG |
   | Program dump | ABAP runtime error | Check ST22, fix code |
   | Resource shortage | No available WP or memory | Reschedule to off-peak, increase resources |
   | Lock conflict | Table locked by another job | Serialize conflicting jobs |
   | Timeout | Job exceeded max runtime | Investigate code, increase timeout |

3. **Prevent recurrence**:
   - Set up job monitoring in RZ20 (CCMS)
   - Configure event-based scheduling instead of time-based where possible (`SM62`)
   - Review job chains for proper dependency management

**Effort**: Low to Medium (depends on root cause)
**Priority**: Immediate for business-critical job chains

---

### REM-BATCH-02: Batch Window Contention

**Symptoms**: Background WP utilization > 90%, dialog response degradation during
batch windows, job queue delays > 30 minutes.

**Remediation Steps**:

1. **Analyze batch schedule**: `SM36` / SM37
   - Map all jobs by hour — identify peak batch window
   - Check for unnecessary overlaps

2. **Implement operation modes**: `RZ04`
   - Day mode: more dialog WPs, fewer batch WPs
   - Night mode: fewer dialog WPs, more batch WPs
   - Configure automatic switching via `SM63`

3. **Redistribute batch load**:
   - Move non-critical jobs to off-peak hours
   - Distribute jobs across multiple app servers
   - Consider a dedicated batch server instance

4. **Optimize long-running jobs**:
   - Use parallel processing where supported (e.g., MRP, billing)
   - Break large jobs into smaller chunks
   - Use batch events for dependency chains instead of fixed time scheduling

**Effort**: Medium (scheduling changes + operation mode setup)
**Priority**: Short-term

---

## Security Remediation

### REM-SEC-01: SAP_ALL in Production

**Symptoms**: Users with SAP_ALL profile assigned in production systems.

**Root Cause**: Usually a legacy issue — someone needed emergency access during
go-live or an incident and SAP_ALL was never removed.

**Remediation Steps**:

1. **Identify affected users**: `SUIM` → Users by Complex Selection Criteria
   → by Profile → SAP_ALL
2. **For each user**:
   - Determine if the user actually needs elevated access
   - Create a proper role with only the required authorizations via `PFCG`
   - Remove SAP_ALL from the user via `SU01` → Profiles tab
3. **Prevent future assignments**:
   - Configure authorization check for SAP_ALL assignment (SU01 enhancement)
   - Set up monitoring alert in RZ20 for new SAP_ALL assignments
4. **Document the change** — this is often audit-relevant

**Effort**: Medium (requires role design for each affected user)
**Priority**: Immediate (compliance and audit risk)

---

### REM-SEC-02: Default Passwords

**Symptoms**: Standard SAP users (SAP*, DDIC, TMSADM, EARLYWATCH, etc.) still
have factory-default passwords.

**Remediation Steps**:

1. **Run the check report**: `RSUSR003` or `SUIM` → Users with default passwords
2. **Change passwords immediately** for all identified users via `SU01`
3. **Lock unnecessary standard users** in production:
   - SAP* should be locked in all clients (but NOT deleted)
   - DDIC should be locked in production clients (keep unlocked in 000)
   - EARLYWATCH can be locked if not actively used
4. **Set password policy** to prevent trivial passwords:
   - `login/min_password_lng` = 8 (minimum)
   - `login/min_password_specials` = 1
   - `login/min_password_digits` = 1
   - `login/password_expiration_time` = 90

**Effort**: Low (password changes are quick)
**Priority**: Immediate

---

### REM-SEC-03: RFC Destination Security

**Symptoms**: RFC destinations configured without authentication, using stored
plaintext credentials, or pointing to decommissioned systems.

**Remediation Steps**:

1. **Audit all RFC destinations**: `SM59`
   - List all destinations by type (3=ABAP, H=HTTP, G=External)
   - Check authentication method for each
   - Test connectivity — identify dead destinations

2. **Secure or remove each destination**:

   | Finding | Action |
   |---------|--------|
   | No authentication | Configure trusted RFC or stored credentials |
   | Stored credentials with SAP_ALL user | Change to a service user with minimal auth |
   | Destination to decommissioned system | Delete the destination |
   | HTTP destination without SSL | Configure SSL certificates |

3. **Configure gateway security** (if not already done):
   - Set `gw/sec_info` → secinfo file (whitelist allowed programs)
   - Set `gw/reg_info` → reginfo file (whitelist allowed registrations)
   - Test in monitor mode first (`gw/sim_mode = 1`)

**Effort**: Medium (audit + remediation for each destination)
**Priority**: Short-term (High for destinations without any authentication)

---

## System Maintenance Remediation

### REM-MAINT-01: Kernel/Support Package Update

**Symptoms**: Kernel older than 12 months, support packages older than 24 months.

**Remediation Steps**:

1. **Check current levels**: `SM51` (kernel), `SPAM` (support packages)
2. **Review SAP Notes**: Check for security-relevant notes in your current stack
3. **Plan the update**:
   - Kernel update: Download from SAP Support Portal → replace kernel files →
     restart. Can be done per-instance.
   - Support Package: `SPAM` → import queue → requires downtime
4. **Execute in landscape order**: Dev → QA → Pre-Prod → Prod
5. **Test thoroughly**: Run regression tests after each environment update

**Effort**: High (planning, coordination, testing, downtime)
**Priority**: Medium-term (unless security-critical notes are outstanding → Immediate)

---

### REM-MAINT-02: System Log Cleanup

**Symptoms**: Excessive ABAP dumps (> 50/day in ST22), recurring error patterns
in SM21, growing dump file size.

**Remediation Steps**:

1. **Analyze dump patterns**: `ST22` → sort by program, date
   - Identify the top 5 recurring dump types
   - Distinguish between systematic (code bug) and transient (resource/timeout)

2. **For systematic dumps** (same program, same error, repeating):
   - File as an ABAP developer task
   - Check SAP Notes for known issues (search on the program name and dump type)
   - Common dumps and shortcuts:
     - `DBIF_RSQL_SQL_ERROR`: Database issue → check DB logs
     - `TSV_TNEW_PAGE_ALLOC_FAILED`: Memory exhaustion → see REM-MEM-01
     - `TIME_OUT`: Long-running statement → optimize code or increase timeout
     - `RAISE_EXCEPTION` / `ASSERTION_FAILED`: Application bug → developer fix

3. **Configure dump auto-cleanup**:
   - `ST22` → Reorganize → set retention to 14-30 days
   - Schedule `RSNAPH00` as periodic batch job for automatic cleanup

**Effort**: Low (cleanup) to High (fixing root causes)
**Priority**: Medium-term

---

## Storage & Housekeeping Remediation

### REM-HOUSE-01: Spool/TemSe Cleanup

**Symptoms**: TemSe objects > 50,000, spool requests older than 30 days,
TEMSE-related space consumption growing.

**Remediation Steps**:

1. **Analyze current state**: `SP12` → TemSe administration
2. **Clean up old entries**:
   - `RSPO_TEMSE_DELETE` — delete orphaned TemSe objects
   - `SP12` → Consistency Check → delete inconsistent entries
3. **Configure automatic cleanup**:
   - `RSPO_CHECK_TEMSE_CONSISTENCY` — schedule weekly
   - Set spool retention: `rdisp/max_spool_prods` (max spool requests per user)
   - Set spool lifetime: `rspo/store_days_for_finished` = 7

**Effort**: Low
**Priority**: Short-term

---

### REM-HOUSE-02: Transport Log Cleanup

**Symptoms**: Large transport directory, old transport requests accumulating,
import queue backlog.

**Remediation Steps**:

1. **Clean transport directory**:
   - `STMS` → check completed transports older than 90 days
   - Use TP command `tp check` to identify orphaned transport files
   - Delete data/cofiles for fully imported, released transports

2. **Process import queue**:
   - Review and import or reject pending transports
   - Remove outdated requests from the queue

3. **Configure retention**: Set transport directory cleanup schedule

**Effort**: Low
**Priority**: Medium-term

---

## Effort Estimation Guide

Use these definitions when assigning effort to remediation actions:

| Effort Level | Definition | Typical Timeframe | Examples |
|-------------|-----------|-------------------|---------|
| **Low** | Parameter change, configuration toggle, or cleanup task. Can be done by one Basis admin. May require planned restart. | 1–4 hours | Buffer size increase, password change, spool cleanup |
| **Medium** | Requires planning, coordination with other teams, or multi-step procedure. May need change management process. | 1–5 days | Index creation, job rescheduling, RFC security audit, operation mode setup |
| **High** | Requires development work, significant testing, or downtime coordination. Involves multiple teams (Basis + Dev + functional). | 1–4 weeks | Kernel upgrade, ABAP code optimization, archiving implementation, hardware upgrade |

### Priority vs. Effort Matrix

When both severity and effort are known, use this matrix to recommend scheduling:

| | Low Effort | Medium Effort | High Effort |
|---|---|---|---|
| **Critical** | Fix immediately | Fix within 48 hours | Emergency project — start immediately, accept partial fix |
| **High** | Fix this week | Plan for next 2 weeks | Schedule for next maintenance window |
| **Medium** | Fix in next maintenance | Plan for next sprint | Backlog for next project cycle |
| **Low** | Fix when convenient | Backlog | Backlog — consider if ROI justifies the effort |
