---
name: backend-code-review
description: >
  Comprehensive code review for the EWA Analyzer Python backend. Covers
  FastAPI patterns, async correctness, Azure client usage, AI agent patterns,
  security (XSUAA / CORS / JWT), configuration hygiene, error handling, logging,
  and Python 3.12 type annotation style. Use this skill whenever the user asks to
  review, audit, or inspect any file under backend/ — including routers, agents,
  services, core modules, utils, and workflow orchestrator code. Also trigger for
  questions like "is this code OK?", "check my changes", or "what's wrong with
  this file?" when in the backend directory context.
---

# Backend Code Review Skill

You are reviewing Python 3.12 backend code for the SAP EWA Analyzer — a FastAPI
service that orchestrates multiple AI providers (Azure OpenAI, Anthropic Claude via
Azure AI Foundry) to analyse SAP Early Watch Alert reports. Before reviewing, read
the file(s) completely with `read_file`, then apply the checklist below. Report each
finding with: **file + line range**, **severity** (Critical / High / Medium / Low /
Info), **category**, and a concrete **fix** (code snippet or clear instruction).
Group findings by severity, most severe first.

---

## Checklist

### 1. Security

**1.1 XSUAA / JWT**
- The `XSUAAMiddleware` in `core/xsuaa_middleware.py` is the sole auth gate for
  Cloud Foundry deployments. Never add raw `/api/*` routes to `_PUBLIC_PATHS`
  without explicit justification.
- JWT claims must be verified: `issuer`, `audience`, `exp`, and `scope`. Flag any
  `verify=False` or disabled expiry checks.
- Public-key refresh happens at startup only. Flag any code that exposes JWKS
  endpoints without auth.

**1.2 CORS**
- `CORS_ALLOWED_ORIGINS` must come from the `CORS_ALLOWED_ORIGINS` env var, never
  hardcoded. Wildcard `"*"` origins are not acceptable in routers or middleware.

**1.3 Secrets & Credentials**
- No connection strings, API keys, or tokens in source files. All secrets must be
  read from `os.getenv(...)`. Flag any string literal that looks like a key
  (`sk-...`, `DefaultEndpointsProtocol=...`, `Bearer ...`).

**1.4 Input Validation**
- All HTTP request bodies must be typed Pydantic `BaseModel` subclasses. Never
  accept raw `dict` or `Any` from a request body. Query parameters that take
  user-provided paths or blob names should be validated (no path traversal).

**1.5 Azure Blob Safety**
- Blob names derived from user input must not allow `../` path traversal. Check
  that deletions are scoped with `name_starts_with=base_name` (not the whole
  container), as done in `ai_router.py`.

---

### 2. Async Correctness

This is the single most common source of latency regressions in this codebase.

- **Blocking SDK calls in `async def`**: The Azure Blob Storage SDK used here is
  **synchronous**. Every `blob_client.upload_blob(...)`, `blob_client.download_blob().readall()`,
  `list_blobs(...)` etc. must be wrapped in `asyncio.to_thread(...)` or replaced
  with the async `azure-storage-blob` `aio` variant if performance matters.
- **`requests.get` in async context**: `core/xsuaa_middleware.py` calls
  `requests.get` during startup (acceptable) and during `dispatch`. Any call
  inside an `async def` request handler must use `httpx.AsyncClient` instead.
- **`asyncio.run()` inside async code**: Signals a sync/async boundary mistake.
  Flag immediately — use `await` instead.
- **Missing `await`**: Unawaited coroutines silently do nothing. Flag any
  coroutine call that lacks `await`.

---

### 3. Azure Client Hygiene

- **Single shared client**: The BlobServiceClient singleton lives in
  `core/azure_clients.py`. All modules must import `blob_service_client` from
  there. Flag any `BlobServiceClient.from_connection_string(...)` call outside
  `core/azure_clients.py` (there is currently a duplicate initialisation in
  `ewa_main.py` — always flag).
- **None checks**: `blob_service_client` can be `None` if initialisation fails.
  Every usage must guard with `if blob_service_client is None: raise HTTPException(503)`.
- **Connection string over managed identity**: Prefer managed identity
  (`DefaultAzureCredential`) for production; flag plain connection strings in
  non-.env files.

---

### 4. AI Agent Patterns

**4.1 LLM Output Validation**
- Every agent that calls an LLM for structured JSON must:
  1. Validate against a JSON schema (via `jsonschema.validate`).
  2. Use `JSONRepair` from `utils/json_repair.py` as a fallback before raising.
  3. Log the raw LLM response at `DEBUG` level before validation to aid debugging.
- Flag agents that accept LLM JSON without schema validation or repair.

**4.2 Prompt Loading**
- Prompts must be loaded from `.md` files in `backend/prompts/`, not embedded as
  inline Python strings. Inline prompts > 3 lines are a maintenance liability.

**4.3 Parallel Specialist Calls**
- Multiple specialist agents must run with `asyncio.gather(...)`, not sequential
  `await agent.run(...)` calls. Flag sequential patterns.

**4.4 Token / Model Config**
- Model names, `max_tokens`, `reasoning_effort`, and timeouts must come from
  `core/runtime_config.py` constants. No hardcoded values in agent constructors.

**4.5 Retry / Timeout**
- Check that API calls have a timeout set (via `ANTHROPIC_TIMEOUT_SECONDS`,
  `ANTHROPIC_CONNECT_TIMEOUT_SECONDS`, or equivalent). Calls without timeouts
  risk hanging workers indefinitely.

---

### 5. Error Handling

- **Bare `except:`**: Never acceptable. Use `except Exception as exc:` at minimum,
  with a `logger.exception(...)` or `logger.error("...", exc)` call.
- **Swallowed exceptions**: `except Exception: pass` or `except Exception: return None`
  without logging is always a bug. Flag it.
- **HTTPException mapping**: Agent/service exceptions should be caught in the router
  and re-raised as `HTTPException` with an appropriate status code. Don't let raw
  `ValueError`, `KeyError`, or Azure SDK errors reach the client.
- **FastAPI background tasks**: Exceptions in `BackgroundTask` calls are silently
  discarded. Any non-trivial logic in a background task should have its own
  try/except with logging.

---

### 6. Configuration Hygiene

- All environment-driven tunables (model names, token limits, timeouts, reasoning
  effort) must be declared in `core/runtime_config.py` and imported from there.
- `os.getenv(...)` calls with magic default strings (e.g., `os.getenv("MODEL", "gpt-4.1")`)
  scattered across agents or routers are a duplication smell — move them to
  `runtime_config.py`.
- `load_dotenv()` should only be called once, in `ewa_main.py` or the module
  that bootstraps the process. Flag duplicate `load_dotenv()` calls in routers
  or agents.

---

### 7. Logging

- Logger instances must be obtained with `logging.getLogger(__name__)` — never
  `logging.getLogger("my_module")` with a hardcoded name.
- Log messages must not contain PII (user names, email, document content excerpts
  longer than 50 chars). Flag `logger.info(f"content={content}")` patterns.
- Use `%`-style formatting (`logger.info("msg %s", var)`) rather than f-strings
  in log calls — avoids string interpolation when the log level is suppressed.
- `print()` statements in production code are flag-worthy; replace with `logger.debug(...)`.

---

### 8. Type Annotations (Python 3.12 style)

The project targets Python 3.12. Use modern built-in generics:

| Old (pre-3.10) | Preferred (3.10+) |
|---|---|
| `Optional[str]` | `str \| None` |
| `List[str]` | `list[str]` |
| `Dict[str, Any]` | `dict[str, Any]` |
| `Tuple[int, ...]` | `tuple[int, ...]` |
| `Union[A, B]` | `A \| B` |

- All public function signatures should have type annotations.
- `from __future__ import annotations` at the top of each module enables forward
  references and is already the project norm — flag any new file that omits it.

---

### 9. Module & Separation of Concerns

```
routers/     ← HTTP: parse request, call service/orchestrator, return HTTP response
services/    ← Storage I/O: BlobStorage read/write, no business logic
agent/       ← AI: call LLM, validate output, return typed dataclass
workflow_orchestrator.py  ← Wiring: sequence agents, persist results
core/        ← Shared infrastructure: config, clients, middleware, logging
utils/       ← Pure helpers: JSON repair, Excel builder, markdown utils
```

- **Routers must not call AI agents directly** — route through the orchestrator.
- **Agents must not call Azure Blob Storage** — delegate to services.
- **Services must not know about FastAPI** — no `HTTPException` in `services/`.
- Flag any module that imports across the wrong layer.

---

### 10. Code Quality (Minor but worth noting)

- **Dead imports**: Flag unused imports at the top of a module.
- **Docstrings**: Public classes and non-trivial functions should have a one-line
  docstring explaining *what* they do (not *how*).
- **Magic numbers**: Inline literals like `200`, `500`, `0.85` in business logic
  should be named constants.
- **Dataclass vs Pydantic**: Use `dataclasses.dataclass` for internal data transfer
  objects; use `pydantic.BaseModel` for HTTP request/response payloads.
- **File encoding**: All `open(...)` calls must specify `encoding="utf-8"`.

---

## Output Format

Structure your review as follows:

```
## Code Review: <filename(s)>

### Summary
<2–3 sentence overview of overall code quality and the biggest concern>

### Findings

#### 🔴 Critical
- **[SEC-1]** <file>:<lines> — <description> → Fix: <concrete action>

#### 🟠 High
- **[ASYNC-1]** <file>:<lines> — <description> → Fix: <concrete action>

#### 🟡 Medium
- ...

#### 🔵 Low / Info
- ...

### What's Done Well
<Briefly call out patterns that are correct and worth preserving>
```

Use category codes: `SEC` (security), `ASYNC` (async), `AZURE` (Azure clients),
`AI` (agent patterns), `ERR` (error handling), `CFG` (config), `LOG` (logging),
`TYPE` (type annotations), `ARCH` (architecture), `QUAL` (quality).

If no issues are found in a severity tier, omit that tier. Keep fixes actionable —
prefer code snippets over vague instructions.
