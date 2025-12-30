# SAP BTP Migration Guide: EWA Analyzer

## Table of Contents
1. [Overview](#overview)
2. [Architecture Comparison](#architecture-comparison)
3. [SAP BTP Concepts](#sap-btp-concepts)
4. [Migration Strategy](#migration-strategy)
5. [Prerequisites](#prerequisites)
6. [Step-by-Step Migration](#step-by-step-migration)
7. [Configuration Files Explained](#configuration-files-explained)
8. [Deployment Options](#deployment-options)
9. [Security & Authentication](#security--authentication)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This guide walks you through migrating the SAP EWA Analyzer application from **Azure Web Apps** to **SAP Business Technology Platform (BTP)**. The application consists of:

- **Frontend**: SAPUI5 application (currently served via nginx)
- **Backend**: Python FastAPI API server
- **Storage**: Azure Blob Storage (can be kept or migrated)
- **AI Services**: Azure OpenAI and Anthropic (accessed via destinations)

### Why SAP BTP?

| Benefit | Description |
|---------|-------------|
| **Native SAP Integration** | Seamless integration with S/4HANA, ECC, and other SAP systems |
| **Enterprise Security** | Built-in identity management via SAP IAS/XSUAA |
| **Fiori Launchpad** | Deploy as a tile in SAP Fiori Launchpad |
| **Centralized Management** | Single cockpit for all SAP cloud applications |
| **Compliance** | SAP-certified infrastructure for enterprise compliance |

---

## Architecture Comparison

### Current Architecture (Azure)

```
┌─────────────────────────────────────────────────────────────────┐
│                        AZURE CLOUD                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │  Azure Web App   │         │  Azure Web App   │              │
│  │  (Frontend)      │ ──────▶ │  (Backend)       │              │
│  │  SAPUI5 + nginx  │         │  FastAPI Python  │              │
│  └──────────────────┘         └────────┬─────────┘              │
│                                        │                         │
│                    ┌───────────────────┼───────────────────┐    │
│                    │                   │                   │    │
│                    ▼                   ▼                   ▼    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Azure Blob      │  │  Azure OpenAI    │  │  Azure AI    │  │
│  │  Storage         │  │  (GPT-5/Claude)  │  │  Doc Intel   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Target Architecture (SAP BTP)

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAP BTP                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    SAP Build Work Zone                    │   │
│  │                  (Fiori Launchpad)                        │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │                    App Router                             │   │
│  │           (Authentication & Routing)                      │   │
│  └────────────┬─────────────────────────────┬───────────────┘   │
│               │                             │                    │
│  ┌────────────▼──────────┐    ┌─────────────▼────────────┐      │
│  │  HTML5 App Repository │    │  Cloud Foundry App       │      │
│  │  (SAPUI5 Frontend)    │    │  (Python Backend)        │      │
│  └───────────────────────┘    └─────────────┬────────────┘      │
│                                             │                    │
│               ┌─────────────────────────────┼──────────────┐    │
│               │                             │              │    │
│  ┌────────────▼──────────┐    ┌─────────────▼────────────┐│    │
│  │  Destination Service  │    │  SAP AI Core /           ││    │
│  │  (Azure Blob, etc.)   │    │  Generative AI Hub       ││    │
│  └───────────────────────┘    └──────────────────────────┘│    │
│                                                            │    │
└────────────────────────────────────────────────────────────┘    │
                              │                                    │
           ┌──────────────────┴──────────────────┐                │
           ▼                                     ▼                 │
┌──────────────────┐              ┌──────────────────┐            │
│  Azure Blob      │              │  Azure OpenAI    │            │
│  Storage         │              │  (via Destination)│           │
└──────────────────┘              └──────────────────┘            │
```

---

## SAP BTP Concepts

### 1. Cloud Foundry Environment

**What is it?**
Cloud Foundry (CF) is a Platform-as-a-Service (PaaS) runtime on SAP BTP. It allows you to deploy applications written in various languages (Python, Node.js, Java, Go) without managing infrastructure.

**Key Concepts:**
- **Organization (Org)**: Top-level container, typically one per company/team
- **Space**: Subdivision within an org (e.g., dev, test, prod)
- **Application**: Your deployed code (backend, frontend)
- **Service Instance**: Managed services bound to your app (database, storage, etc.)
- **Buildpack**: Runtime environment for your language (Python buildpack for FastAPI)

**Example Structure:**
```
SAP BTP Subaccount
└── Cloud Foundry Environment
    └── Organization: my-company
        ├── Space: dev
        │   ├── App: ewa-backend
        │   ├── App: ewa-frontend
        │   └── Service: destination-instance
        ├── Space: test
        └── Space: prod
```

### 2. App Router

**What is it?**
The App Router is a Node.js-based reverse proxy that:
- Handles authentication via XSUAA (OAuth2/JWT)
- Routes requests to backend services
- Serves static content from HTML5 Application Repository
- Manages user sessions

**Why do you need it?**
- Centralizes authentication before requests hit your backend
- Provides single entry point for your application
- Required for Fiori Launchpad integration

**How it works:**
```
User Request → App Router → XSUAA (Auth Check) → Your Backend/Frontend
```

### 3. XSUAA (Authorization & Trust Management)

**What is it?**
XSUAA is SAP's OAuth2 authorization server. It:
- Issues JWT tokens after user authentication
- Validates tokens on API requests
- Manages scopes and roles for authorization

**Key Terms:**
- **xsappname**: Unique identifier for your application
- **Scopes**: Permissions (e.g., `read`, `write`, `admin`)
- **Role Templates**: Groups of scopes
- **Role Collections**: Assigned to users in BTP Cockpit

### 4. HTML5 Application Repository

**What is it?**
A managed service to store and serve static web content (HTML, JS, CSS). Your SAPUI5 app lives here instead of nginx.

**Benefits:**
- No container to manage for frontend
- Automatic CDN/caching
- Integrated with App Router
- Version management

### 5. Destination Service

**What is it?**
A service that manages connections to external systems. Instead of hardcoding URLs and credentials, you configure "destinations" in the BTP cockpit.

**Use Cases for EWA Analyzer:**
- Connect to Azure Blob Storage
- Connect to Azure OpenAI API
- Connect to Azure Document Intelligence

**Benefits:**
- Credentials stored securely (not in code)
- Easy to change endpoints per environment
- Supports various authentication types (OAuth, API Key, Certificate)

### 6. SAP AI Core / Generative AI Hub

**What is it?**
SAP's managed AI infrastructure that can:
- Host your own ML models
- Proxy to external LLMs (Azure OpenAI, OpenAI, etc.)
- Provide a unified API for AI services

**For EWA Analyzer:**
You can either:
1. Use Destination Service to call Azure OpenAI directly
2. Use Generative AI Hub as a proxy (recommended for enterprise)

---

## Migration Strategy

### Recommended Approach: Hybrid Migration

We'll use a **phased approach** that minimizes risk:

| Phase | Component | Strategy |
|-------|-----------|----------|
| **Phase 1** | Backend | Deploy to Cloud Foundry (Python buildpack) |
| **Phase 2** | Frontend | Deploy to HTML5 App Repository |
| **Phase 3** | Storage | Keep Azure Blob via Destination Service |
| **Phase 4** | AI Services | Keep Azure OpenAI via Destination (or migrate to AI Core) |
| **Phase 5** | Authentication | Add XSUAA for enterprise SSO |
| **Phase 6** | Launchpad | Integrate with SAP Build Work Zone |

### Why Keep Azure Services Initially?

1. **Lower Risk**: Minimize variables during migration
2. **No Data Migration**: Existing files stay in Azure Blob
3. **Same AI Models**: Keep using GPT-5/Claude
4. **Rollback Option**: Can switch back easily if issues arise

Later, you can optionally:
- Migrate storage to SAP Object Store Service
- Switch AI to SAP Generative AI Hub

---

## Prerequisites

### SAP BTP Requirements

1. **SAP BTP Account** with:
   - Cloud Foundry environment enabled
   - Entitlements for:
     - HTML5 Application Repository
     - Destination Service
     - Authorization & Trust Management (XSUAA)
     - (Optional) SAP AI Core

2. **Cloud Foundry CLI** installed:
   ```bash
   # macOS
   brew install cloudfoundry/tap/cf-cli@8
   
   # Windows (via Chocolatey)
   choco install cloudfoundry-cli
   
   # Or download from: https://github.com/cloudfoundry/cli/releases
   ```

3. **MTA Build Tool** (for multi-target applications):
   ```bash
   npm install -g mbt
   ```

4. **Cloud MTA Build Tool** (optional, for CI/CD):
   ```bash
   npm install -g @sap/mta
   ```

### Verify Prerequisites

```bash
# Check CF CLI
cf version

# Check MTA Build Tool
mbt --version

# Login to SAP BTP Cloud Foundry
cf login -a https://api.cf.<region>.hana.ondemand.com

# Example regions:
# - eu10 (Europe - Frankfurt)
# - us10 (US East - VA)
# - ap10 (Australia - Sydney)
```

---

## Step-by-Step Migration

### Step 1: Project Structure Setup

Create the following BTP-specific files in your project root:

```
ewa_analyzer/
├── mta.yaml                    # Multi-Target Application descriptor
├── xs-security.json            # XSUAA security configuration
├── backend/
│   ├── manifest.yaml           # CF deployment manifest
│   ├── runtime.txt             # Python version for buildpack
│   ├── Procfile                # Process startup command
│   └── ... (existing code)
├── sapui5/
│   ├── xs-app.json             # App Router routes (in webapp/)
│   └── ... (existing code)
└── approuter/
    ├── package.json            # App Router dependencies
    └── xs-app.json             # Routing configuration
```

### Step 2: Configure MTA Descriptor

The `mta.yaml` file defines your entire application stack. See the generated file for details.

### Step 3: Configure XSUAA Security

The `xs-security.json` defines authentication and authorization. See the generated file for details.

### Step 4: Update Backend for Cloud Foundry

Key changes needed:
1. Read port from `$PORT` environment variable (CF assigns it)
2. Read services from `$VCAP_SERVICES` (CF service bindings)
3. Add `manifest.yaml` for CF deployment
4. Add `runtime.txt` for Python version
5. Add `Procfile` for startup command

### Step 5: Update Frontend for HTML5 Repository

Key changes needed:
1. Update `manifest.json` with Cloud Foundry routing
2. Create `xs-app.json` for App Router routes
3. Configure API endpoint to use destination

### Step 6: Build and Deploy

```bash
# Build the MTA archive
mbt build

# Deploy to Cloud Foundry
cf deploy mta_archives/ewa-analyzer_1.0.0.mtar
```

---

## Configuration Files Explained

### mta.yaml (Multi-Target Application)

This is the "master" configuration that defines:
- All modules (apps) in your project
- All services (resources) needed
- Dependencies between modules and services

**Sections:**
- `modules`: Your applications (backend, frontend, approuter)
- `resources`: BTP services (XSUAA, destination, HTML5 repo)
- `parameters`: Build and deployment settings

### xs-security.json (XSUAA Configuration)

Defines:
- `xsappname`: Unique identifier
- `scopes`: Permissions your app needs
- `role-templates`: Groups of scopes
- `oauth2-configuration`: Token settings

### manifest.yaml (Cloud Foundry Manifest)

Defines for each CF app:
- Memory allocation
- Disk quota
- Instances count
- Environment variables
- Service bindings
- Routes (URLs)

### xs-app.json (App Router Routes)

Defines how the App Router handles requests:
- Which paths go to which backend
- Authentication requirements per route
- Static file serving

---

## Deployment Options

### Option A: Cloud Foundry (Recommended)

**Pros:**
- Fully managed platform
- Auto-scaling available
- Integrated with BTP services
- No container management

**Cons:**
- Limited to supported buildpacks
- Less control over runtime

### Option B: Kyma (Kubernetes)

**Pros:**
- Full container support
- More control over infrastructure
- Can use existing Dockerfiles

**Cons:**
- More complex to manage
- Requires Kubernetes knowledge
- Higher operational overhead

### Our Choice: Cloud Foundry

For EWA Analyzer, Cloud Foundry is recommended because:
1. Python buildpack supports FastAPI well
2. Simpler deployment model
3. Better integration with HTML5 Repository
4. Lower operational complexity

---

## Security & Authentication

### Authentication Flow

```
1. User accesses App Router URL
2. App Router redirects to XSUAA login
3. User authenticates (SAP IAS, Azure AD, etc.)
4. XSUAA issues JWT token
5. App Router forwards request with JWT to backend
6. Backend validates JWT and processes request
```

### Configuring Identity Provider

In BTP Cockpit:
1. Go to **Security** → **Trust Configuration**
2. Add your identity provider (SAP IAS, Azure AD, etc.)
3. Configure attribute mapping

### Backend JWT Validation

Your FastAPI backend needs to validate JWT tokens from XSUAA. See the updated code for implementation.

---

## Troubleshooting

### Common Issues

**1. "Unauthorized" errors after deployment**
- Check XSUAA service is bound to App Router
- Verify xs-security.json has correct scopes
- Ensure user has role collection assigned

**2. Backend not reachable from frontend**
- Check destination configuration in BTP Cockpit
- Verify xs-app.json routes are correct
- Check backend is running: `cf apps`

**3. Build fails with MTA**
- Ensure all referenced files exist
- Check mta.yaml syntax: `mbt validate`
- Verify Node.js and Python versions

**4. Static files not loading**
- Check HTML5 repo deployment: `cf html5-list`
- Verify App Router xs-app.json routes

### Useful Commands

```bash
# View deployed apps
cf apps

# View app logs
cf logs ewa-backend --recent

# View service instances
cf services

# Restart app
cf restart ewa-backend

# Scale app
cf scale ewa-backend -i 2

# View environment variables
cf env ewa-backend
```

---

## Next Steps

After successful migration:

1. **Set up CI/CD** with GitHub Actions for BTP deployment
2. **Configure monitoring** with SAP Cloud ALM
3. **Integrate with Fiori Launchpad** for enterprise access
4. **Add custom domain** via BTP Custom Domain Service
5. **Consider SAP AI Core** for managed AI infrastructure

---

## Appendix: File Reference

| File | Purpose | Location |
|------|---------|----------|
| `mta.yaml` | MTA descriptor | Project root |
| `xs-security.json` | XSUAA config | Project root |
| `backend/manifest.yaml` | CF manifest for backend | backend/ |
| `backend/runtime.txt` | Python version | backend/ |
| `backend/Procfile` | Startup command | backend/ |
| `approuter/package.json` | App Router deps | approuter/ |
| `approuter/xs-app.json` | Routing config | approuter/ |
| `sapui5/webapp/xs-app.json` | UI5 routing | sapui5/webapp/ |

