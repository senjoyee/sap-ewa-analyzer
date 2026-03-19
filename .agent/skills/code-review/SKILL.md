---
name: code-review
description: Apply comprehensive code review standards including security, performance, maintainability, and best practices across any codebase
---

# Code Review & Quality Standards

When reviewing or writing code, systematically apply these standards:

## 1. Security Review
- **Input Validation**: All user inputs must be validated and sanitized
- **Authentication/Authorization**: Verify proper access controls are in place
- **Secrets Management**: No hardcoded credentials, API keys, or sensitive data
- **SQL Injection**: Use parameterized queries, never string concatenation
- **XSS Prevention**: Properly escape output in web contexts
- **CSRF Protection**: Verify anti-CSRF tokens on state-changing requests
- **CORS Configuration**: Restrict allowed origins; never use wildcard (`*`) with credentials
- **Rate Limiting**: Protect endpoints against brute-force and DoS attacks
- **File Upload Validation**: Validate file type, size, and name; prevent path traversal
- **Insecure Deserialization**: Never deserialize untrusted data without validation
- **PII in Logs**: Ensure sensitive data (passwords, tokens, PII) is never logged
- **SSRF Prevention**: Validate and restrict server-side outbound requests to allowed hosts
- **Encryption**: Enforce TLS in transit; encrypt sensitive data at rest
- **Dependency Vulnerabilities**: Check for known vulnerabilities in dependencies

## 2. Performance Considerations
- **Algorithm Complexity**: Identify O(n²) or worse operations on large datasets
- **Database Queries**: Check for N+1 queries, missing indexes, or inefficient joins
- **Memory Leaks**: Ensure proper disposal of resources (connections, streams, event handlers)
- **Caching**: Suggest caching for expensive repeated operations
- **Lazy Loading**: Defer expensive operations until needed

## 3. Code Quality & Design Principles
- **DRY Principle**: Identify and eliminate code duplication
- **SOLID Principles**:
  - *Single Responsibility*: Each function/class should have one clear purpose
  - *Open/Closed*: Open for extension, closed for modification
  - *Liskov Substitution*: Subtypes must be substitutable for their base types
  - *Interface Segregation*: Prefer small, focused interfaces over large ones
  - *Dependency Inversion*: Depend on abstractions, not concrete implementations
- **Dependency Injection**: Inject dependencies rather than instantiating them internally; improves testability and decoupling
- **Design Patterns**: Apply appropriate patterns (Factory, Strategy, Observer, etc.) but avoid over-engineering
- **Naming**: Use clear, descriptive names that reveal intent
- **Magic Numbers**: Replace with named constants
- **Error Handling**: Proper try-catch blocks with meaningful error messages
- **Logging**: Add appropriate logging for debugging and monitoring

## 4. Maintainability
- **Comments**: Explain *why*, not *what* (code should be self-documenting)
- **Function Length**: Keep functions focused and under ~50 lines
- **Cyclomatic Complexity**: Flag overly complex conditional logic
- **Dependencies**: Minimize coupling between modules
- **Layered Architecture**: Enforce clear separation of concerns (e.g., controller → service → repository)
- **Test Coverage**: Ensure critical paths have tests

## 5. Language-Specific Best Practices

### C# / .NET
- Use `async/await` properly (avoid `.Result` or `.Wait()`)
- Implement `IDisposable` for unmanaged resources
- Use nullable reference types appropriately
- Follow naming conventions (PascalCase for public, camelCase for private)
- Prefer LINQ for collections when readable

### JavaScript/TypeScript
- Use `const` by default, `let` when needed, never `var`
- Avoid callback hell, use Promises or async/await
- Check for null/undefined before accessing properties
- Use TypeScript strict mode when available
- Avoid mutating function parameters

### Python
- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Avoid mutable default arguments
- Use context managers (`with` statement) for resources
- Prefer list comprehensions for simple transformations

### SQL
- Always use parameterized queries
- Include appropriate indexes for WHERE/JOIN columns
- Avoid SELECT *, specify needed columns
- Use transactions for multi-step operations

## 6. Testing Standards
- **Unit Tests**: Test individual functions in isolation
- **Integration Tests**: Test component interactions
- **Edge Cases**: Test boundary conditions, null/empty inputs
- **Error Cases**: Verify proper error handling
- **Test Names**: Should describe what is being tested and expected outcome

## 7. Documentation Requirements
- **Public APIs**: Document parameters, return values, exceptions
- **Complex Logic**: Explain non-obvious algorithms or business rules
- **Breaking Changes**: Clearly mark and document
- **README**: Keep up-to-date with setup and usage instructions

## 8. Git & Version Control
- **Commit Messages**: Use meaningful, descriptive messages
- **Atomic Commits**: Each commit should be a logical unit
- **Branch Naming**: Use descriptive names (feature/, bugfix/, hotfix/)
- **No Commented Code**: Remove dead code instead of commenting

## 9. Concurrency & Thread Safety
- **Race Conditions**: Identify shared mutable state accessed by multiple threads without synchronization
- **Deadlocks**: Watch for circular lock dependencies and inconsistent lock ordering
- **Thread-Safe Collections**: Use concurrent/thread-safe data structures when sharing across threads
- **Atomic Operations**: Use atomic primitives for simple counters/flags instead of full locks
- **Async Correctness**: Avoid mixing sync and async code; never block on async calls
- **Resource Contention**: Minimize lock scope and duration; prefer lock-free designs where feasible

## 10. API Design & Contracts
- **RESTful Conventions**: Use proper HTTP methods, status codes, and resource naming
- **Versioning**: APIs should be versioned (URL path, header, or query param) to avoid breaking consumers
- **Pagination**: Large collections must support pagination (cursor-based preferred over offset)
- **Idempotency**: State-changing operations (PUT, DELETE) should be idempotent; use idempotency keys for POST
- **Request/Response Validation**: Validate schemas at API boundaries; return structured error responses
- **Contract Testing**: Ensure API changes don't break existing consumers; use contract tests or OpenAPI specs

## 11. Resilience & Fault Tolerance
- **Retry Logic**: Use exponential backoff with jitter for transient failures; cap max retries
- **Circuit Breakers**: Protect downstream services from cascading failures
- **Timeouts**: Set explicit timeouts on all external calls (HTTP, DB, queues); never wait indefinitely
- **Graceful Degradation**: Provide fallback behavior when dependencies are unavailable
- **Bulkheading**: Isolate failure domains so one failing component doesn't take down the entire system
- **Health Checks**: Expose liveness and readiness endpoints for orchestrators

## 12. Observability
- **Structured Logging**: Use key-value structured logs (JSON) instead of free-text; include correlation IDs
- **Distributed Tracing**: Propagate trace context across service boundaries (OpenTelemetry, etc.)
- **Metrics & Alerting**: Instrument key business and technical metrics (latency, error rate, throughput)
- **Error Reporting**: Integrate with error tracking systems (Sentry, Application Insights, etc.)
- **Audit Logging**: Log security-relevant events (login, permission changes, data access) separately

## 13. Configuration Management
- **Environment Separation**: No environment-specific values in code; use env vars or config services
- **Config Validation**: Validate required configuration at startup; fail fast on missing values
- **Feature Flags**: Use feature flags for gradual rollouts and safe deployments
- **Secret Rotation**: Support rotating secrets without redeployment

## 14. Data Integrity & Backwards Compatibility
- **Validation at Boundaries**: Validate all data at system entry points (API, message consumers, file imports)
- **Database Migrations**: Migrations must be backwards-compatible; avoid destructive schema changes without a migration plan
- **API Backwards Compatibility**: Additive changes only; deprecate before removing fields/endpoints
- **Idempotent Mutations**: Ensure retried operations don't cause duplicate side effects
- **Data Consistency**: Use transactions for multi-step operations; consider eventual consistency trade-offs

## 15. Accessibility (Frontend)
- **Semantic HTML**: Use proper elements (`<button>`, `<nav>`, `<main>`) instead of generic `<div>`
- **ARIA Attributes**: Add `aria-label`, `aria-describedby`, roles where semantic HTML is insufficient
- **Keyboard Navigation**: All interactive elements must be reachable and operable via keyboard
- **Color Contrast**: Meet WCAG AA minimum contrast ratios (4.5:1 for text, 3:1 for large text)
- **Screen Reader Testing**: Verify content is announced correctly by assistive technology
- **Focus Management**: Maintain logical focus order; trap focus in modals; restore focus on close

## 16. Internationalization & Localization
- **Externalized Strings**: No user-facing strings hardcoded in source; use i18n resource bundles
- **Timezone Handling**: Store and transmit times in UTC; convert to local time only at the presentation layer
- **Character Encoding**: Use UTF-8 consistently across storage, transmission, and display
- **Date/Number Formatting**: Use locale-aware formatters; never assume a single date or number format
- **RTL Support**: Account for right-to-left languages in layout and text alignment if applicable

## 17. Docker & Deployment Hygiene
- **Multi-Stage Builds**: Minimize image size by separating build and runtime stages
- **Non-Root Containers**: Run processes as a non-root user inside containers
- **`.dockerignore`**: Exclude unnecessary files (node_modules, .git, local configs) from build context
- **Image Scanning**: Scan container images for vulnerabilities in CI/CD
- **Health Probes**: Configure liveness, readiness, and startup probes for orchestrated deployments
- **Reproducible Builds**: Pin dependency versions and base image tags; avoid `latest`

## Review Checklist
When reviewing code, systematically check:
- [ ] Security vulnerabilities addressed (including CSRF, CORS, rate limiting, encryption)
- [ ] Performance bottlenecks identified
- [ ] Code is DRY and follows SOLID principles
- [ ] Error handling is comprehensive
- [ ] Concurrency issues addressed (race conditions, deadlocks, thread safety)
- [ ] API contracts are stable, versioned, and validated
- [ ] Resilience patterns applied (retries, timeouts, circuit breakers)
- [ ] Tests cover critical functionality and edge cases
- [ ] Observability in place (structured logging, tracing, metrics)
- [ ] Configuration externalized and validated at startup
- [ ] Data integrity enforced at boundaries; migrations are backwards-compatible
- [ ] Documentation is clear and current
- [ ] No hardcoded values or secrets
- [ ] Resource cleanup is proper
- [ ] Naming is clear and consistent
- [ ] Accessibility standards met (if frontend)
- [ ] i18n/l10n handled (externalized strings, UTC times, locale-aware formatting)
- [ ] Container/deployment hygiene verified (non-root, pinned versions, health probes)
- [ ] Code follows project conventions

## When to Apply This Skill
Use this skill when:
- Reviewing pull requests or code changes
- Writing new code from scratch
- Refactoring existing code
- Debugging issues that may stem from code quality
- Establishing coding standards for a project
