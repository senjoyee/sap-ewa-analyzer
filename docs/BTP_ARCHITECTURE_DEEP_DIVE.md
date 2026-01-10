# SAP BTP Architecture Deep Dive: Technical Reference

**Version**: 1.4  
**Target Audience**: Solutions Architects, Senior Developers, DevOps Engineers  
**Scope**: End-to-end architecture of the EWA Analyzer on SAP BTP Cloud Foundry.

---

## 1. Executive Summary

The EWA Analyzer is a **cloud-native, microservices-based application** deployed on SAP BTP (Cloud Foundry environment). It orchestrates a secure flow between an SAPUI5 frontend, a Python/FastAPI backend, and Azure AI services.

The architecture prioritizes **security** (via XSUAA & Principal Propagation), **scalability** (stateless containers), and **cost-efficiency** (leveraging existing Azure subscriptions for heavy storage/compute).

---

## 2. High-Level Architecture (C4 Container View)

```mermaid
graph TD
    subgraph Client_Layer
        User((User)) -->|HTTPS/TLS 1.2+| LoadBalancer[BTP Load Balancer]
    end

    subgraph BTP_Cloud_Foundry_Space
        LoadBalancer -->|Routes Traffic| AppRouter[App Router<br/>(Node.js / @sap/approuter)]
        
        AppRouter -->|Serve Static Assets| HTML5Repo[HTML5 Repo<br/>(Runtime Service)]
        AppRouter -->|Proxy API + JWT| Backend[Python Backend<br/>(FastAPI / Gunicorn)]
        
        Backend -.->|Validates Token (JKU)| XSUAA[XSUAA Service<br/>(OAuth2 Provider)]
        AppRouter -.->|Auth Flow| XSUAA
    end
    
    subgraph External_Hyperscaler_Azure
        Backend -->|HTTPS / API Key| OpenAI[Azure OpenAI<br/>(GPT-4o)]
        Backend -->|HTTPS / SAS| Blob[Azure Blob Storage<br/>(Persistence)]
    end
    
    subgraph Identity_Provider
        XSUAA -.->|Federation| IAS[Identity Authentication Service<br/>(IAS)]
    end
```

---

## 3. Component Deep Dive

### A. The Standalone Application Router (`@sap/approuter`)
*Pattern: Backend for Frontend (BFF) / Reverse Proxy*

We utilize the **Standalone AppRouter** pattern running as a Node.js microservice.

**Responsibilities:**
1.  **Session Termination**: Maintains the user session via encrypted `JSESSIONID` cookies.
2.  **OAuth2 Orchestration**: Handles the complex Authorization Code flow with XSUAA.
3.  **Token Refresh**: Automatically refreshes expired Access Tokens using the Refresh Token.
4.  **Route Dispatch**:
    -   `/index.html` → HTML5 Repo (UI)
    -   `/api/*` → Python Backend (API)
5.  **Security Headers**: Injects `X-Frame-Options`, `Content-Security-Policy`, and prevents CSRF attacks.

### B. Python Cloud Foundry Runtime
*Pattern: Stateless Microservice*

The core logic resides in a **FastAPI** application containerized via the standard `python_buildpack`.

**Runtime Characteristics:**
-   **Concurrency**: Runs `gunicorn` with `uvicorn` workers for asynchronous request handling (essential for I/O-bound AI calls).
-   **Ephemeral Storage**: The container filesystem is volatile. All state is offloaded to Azure Blob Storage.
-   **Config Injection**: Uses `mtaext.yaml` to inject Azure credentials as environment variables at deployment time.

### C. Connectivity & Destination Service
*Pattern: Service Registry / Proxy*

The Destination Service abstracts physical URLs from the code.

-   **Destination**: `backend-api`
-   **Property**: `HTML5.ForwardAuthToken=true`
-   **Mechanism**: The App Router asks the Destination Service "Where is backend-api?". The service responds with the URL and an instruction to **propagate the user's JWT**. This ensures the backend knows *exactly* who is calling it.

---

## 4. Key Architectural Decisions (ADR)

Why was the system built this way?

### ADR-001: Standalone AppRouter vs. Managed AppRouter
*   **Decision**: Use Standalone AppRouter.
*   **Reasoning**: The Managed AppRouter (SAP Build Work Zone) is simpler but restrictive. The Standalone version allows custom middleware, precise control over `xs-app.json` routing rules (e.g., specific regex overrides for API paths), and independent versioning of the routing layer.

### ADR-002: Python (FastAPI) vs. Node.js (CAP)
*   **Decision**: Use Python with FastAPI.
*   **Reasoning**: While SAP CAP (Node/Java) is standard for business apps, this is an **AI Application**. Python is the native language of AI/ML. Using Python simplifies integration with Azure OpenAI SDKs, PyMuPDF (PDF processing), and data science libraries like Pandas/NumPy.

### ADR-003: Azure Blob Storage vs. SAP Object Store
*   **Decision**: Use Azure Blob Storage directly.
*   **Reasoning**: While BTP offers an Object Store service (wrapper around S3/Azure), connecting directly to Azure Blob Storage reduces latency for the AI processing loop (which also runs on Azure) and allows usage of advanced Azure-specific features (SAS tokens, Lifecycle Management) without an abstraction layer.

### ADR-004: Azure OpenAI vs. SAP AI Core
*   **Decision**: Direct integration with Azure OpenAI.
*   **Reasoning**: 
    -   **Latency**: Removes an extra hop (BTP -> AI Core -> Azure).
    -   **Model Availability**: Direct access to the latest GPT-4o models on Azure often precedes availability in SAP AI Core/Generative AI Hub.
    -   **Cost**: Leverages existing Enterprise Agreement (EA) with Microsoft rather than consuming BTP Cloud Credits.

### ADR-005: "Untagged" HTML5 Repository
*   **Decision**: Deploy UI without `sap.cloud.service` tag.
*   **Reasoning**: This simplifies the routing configuration by removing the need for the `tenants` host pattern and specialized Role Collections for the HTML5 Registry. It treats the UI as a simple static resource served by this specific App Router instance, eliminating 404 errors caused by missing generic scope assignments.

---

## 5. Security Architecture

### Identity & Access Management (IAM)
1.  **Authentication**: Federated via **SAP Cloud Identity Services (IAS)**. BTP does not store passwords.
2.  **Authorization**: Role-Based Access Control (RBAC) enforced via XSUAA Scopes.
    -   **Viewer Role**: Maps to scope `EWA_Analyzer_Viewer`. Allows read-only access to analysis reports.
    -   **Administrator Role**: Maps to scope `EWA_Analyzer_Administrator`. Allows uploading, reprocessing, and deleting reports.
    -   **Enforcement**: The backend middleware decodes the JWT and verifies the presence of these scopes before processing requests.

### Secrets Management
*   **Principle**: "Zero Secrets in Code".
*   **Implementation**:
    -   **Git**: No secrets allowed.
    -   **CI/CD**: Secrets injected from GitHub Actions vault.
    -   **Runtime**: Secrets injected via `VCAP_SERVICES` (for BTP services) or User-Provided Environment Variables (for Azure).
    -   **Access**: Only the specific container instance can read its own environment variables.

---

## 6. Deployment & Automation (CI/CD)

The application lifecycle is automated via **GitHub Actions**.

### The Pipeline (`deploy-to-btp.yml`)
1.  **Checkout**: Pulls code from `main`.
2.  **MTA Build**: Uses `mbt` (Cloud MTA Build Tool) to compile the UI (npm), Backend (pip requirements), and Router into a single `.mtar` archive.
3.  **Inject Secrets**: Generates an ephemeral `mtaext.yaml` using GitHub Secrets (Azure Keys, API Endpoints).
4.  **Deploy**: Authenticates to BTP (Technical User) and runs `cf deploy`.
5.  **Blue-Green Deployment** (Optional Strategy):
    -   BTP starts the new version alongside the old one.
    -   Routes are flipped only after the new version passes health checks.
    -   This enables **Zero Downtime**.

---

## 7. Operations & Observability

### Sizing & Cost Estimation (T-Shirt Sizing)
For a typical production load (approx. 100 concurrent users), we recommend scaling up from the current development baseline.

| Component | Current (Dev) | Recommended (Prod) | Instances (Prod) | Justification |
|-----------|---------------|-------------------|------------------|---------------|
| App Router | 256 MB | 256 MB | 2 | Low CPU footprint; mainly IO. 2 instances for High Availability (HA). |
| Python Backend | 512 MB | 1 GB | 2+ | High Memory consumption during PDF extraction. 512MB is sufficient for functional testing, but 1GB is safer for large documents to avoid OOM kills. |
| **Total Quota** | **~1 GB** | **~3 GB** | - | Includes headroom for blue-green deployment. |

*Note: The current `mta.yaml` is configured for the "Dev" profile (512MB Backend).*

### Autoscaling
We can bind the **SAP BTP Application Autoscaler** service to the Python backend.
-   **Metric**: CPU Utilization > 80% or Throughput > 100 requests/sec.
-   **Action**: Scale out (add instances) up to a defined max (e.g., 5).
-   **Scale In**: When load drops, reduce instances to min (2) to save costs.

### Advanced Troubleshooting (CLI)

**1. Container Access (`cf ssh`)**
Critical for debugging runtime issues or checking injected environment variables.
```bash
cf ssh ewa-analyzer-backend
# Inside container:
env | grep VCAP_SERVICES   # Verify credentials injection
cat logs/app.log           # View local application logs
top                        # Monitor CPU/Memory spikes
curl localhost:8080/health # Local health check
```

**2. UI Deployment Verification**
Verify exactly which version of the UI is currently live in the HTML5 Repo.
```bash
cf html5-list -di ewaanalyzer-repo-host
```

---

## 8. Data Privacy & Resiliency

### Data Residency
-   **BTP Region**: Apps run in `eu10` (Frankfurt, AWS) - Data processing happens here.
-   **Azure Region**: OpenAI and Blob Storage should be pinned to the **same region** (e.g., West Europe) to ensure GDPR compliance (data never leaves the EEA) and minimize latency.
-   **Encryption**: Azure Blob Storage uses AES-256 encryption at rest (Microsoft-managed keys).

### High Availability (HA)
-   **BTP**: Cloud Foundry distributes application instances across **3 Availability Zones (AZs)** automatically. Running `instances: 2` or more ensures that if one AZ goes down, the application remains available.
-   **Azure**: Use **ZRS (Zone-Redundant Storage)** for Blob Storage to match BTP's resiliency level.

---

## 9. Common Architectural Questions

**Q: Why don't we use the Cloud Connector?**
A: Cloud Connector is for accessing on-premise systems (e.g., S/4HANA behind a corporate firewall). Our backend connects to **public cloud services** (Azure OpenAI/Blob), which are accessible via the internet (secured by keys). Thus, no tunnel is required.

**Q: How do we handle "Bad Gateway" (502) errors?**
A: A 502 from the App Router usually means the Backend container is unresponsive.
1.  Check `cf app ewa-analyzer-backend` (Is it running?).
2.  Check `cf logs` (Did it run out of memory (OOM)?).
3.  Check if the startup timeout was exceeded (Python app taking too long to load models).

**Q: Can we run this locally?**
A: Yes, via **Hybrid Testing**.
1.  Run the UI locally (`npm start`).
2.  Run the Backend locally (`uvicorn...`).
3.  Bind to BTP services using `btp-service-binding` or `dotenv` files with credentials from `cf env`.
