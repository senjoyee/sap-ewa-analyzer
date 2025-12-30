# SAP BTP Concepts Tutorial

A deep-dive into SAP Business Technology Platform concepts for developers migrating from Azure.

## Table of Contents

1. [Cloud Foundry Fundamentals](#cloud-foundry-fundamentals)
2. [Multi-Target Applications (MTA)](#multi-target-applications-mta)
3. [App Router Deep Dive](#app-router-deep-dive)
4. [XSUAA Authentication](#xsuaa-authentication)
5. [Destination Service](#destination-service)
6. [HTML5 Application Repository](#html5-application-repository)
7. [Environment Variables & Service Bindings](#environment-variables--service-bindings)

---

## Cloud Foundry Fundamentals

### What is Cloud Foundry?

Cloud Foundry (CF) is an open-source Platform-as-a-Service (PaaS) that SAP uses as the runtime environment in BTP. Think of it as a managed Kubernetes alternative where you focus on code, not infrastructure.

### Comparison: Azure vs Cloud Foundry

| Concept | Azure | Cloud Foundry |
|---------|-------|---------------|
| App hosting | Azure Web App | CF Application |
| Container registry | Azure Container Registry | Not needed (buildpacks) |
| Environment vars | App Settings | `cf set-env` or manifest.yaml |
| Secrets | Azure Key Vault | User-provided services |
| Scaling | Scale settings | `cf scale` |
| Logs | Log Analytics | `cf logs` |
| Health checks | Health probes | CF health checks |

### Key Terminology

```
┌─────────────────────────────────────────────────────────────┐
│                    SAP BTP Subaccount                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Cloud Foundry Environment                 │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │                  Organization                    │  │  │
│  │  │  ┌──────────────┐  ┌──────────────┐            │  │  │
│  │  │  │  Space: dev  │  │  Space: prod │            │  │  │
│  │  │  │  - app1      │  │  - app1      │            │  │  │
│  │  │  │  - app2      │  │  - app2      │            │  │  │
│  │  │  │  - svc1      │  │  - svc1      │            │  │  │
│  │  │  └──────────────┘  └──────────────┘            │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

- **Subaccount**: Your BTP environment, contains entitlements and services
- **Organization**: Top-level CF container (usually one per subaccount)
- **Space**: Isolated environment for apps (dev, test, prod)
- **Application**: Your deployed code
- **Service Instance**: A managed service bound to apps

### Buildpacks vs Containers

**Azure (Containers):**
```dockerfile
FROM python:3.12-slim
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "app:main"]
```

**Cloud Foundry (Buildpacks):**
```yaml
# manifest.yaml
applications:
  - name: my-app
    buildpack: python_buildpack
    # Buildpack detects requirements.txt automatically
```

Buildpacks automatically:
- Detect your language (Python, Node.js, Java, etc.)
- Install dependencies
- Configure the runtime
- Set up health checks

### Essential CF Commands

```bash
# Authentication
cf login -a https://api.cf.eu10.hana.ondemand.com
cf logout

# Navigation
cf target                    # Show current org/space
cf target -o my-org -s dev  # Switch org/space

# Applications
cf apps                      # List apps
cf app my-app               # App details
cf push                      # Deploy (uses manifest.yaml)
cf start/stop/restart my-app
cf delete my-app

# Scaling
cf scale my-app -i 3        # 3 instances
cf scale my-app -m 512M     # 512MB memory

# Logs
cf logs my-app              # Stream logs
cf logs my-app --recent     # Recent logs

# Services
cf services                  # List services
cf create-service xsuaa application my-xsuaa
cf bind-service my-app my-xsuaa
cf unbind-service my-app my-xsuaa

# Environment
cf env my-app               # Show env vars
cf set-env my-app KEY value
cf restage my-app           # Apply env changes
```

---

## Multi-Target Applications (MTA)

### What is MTA?

MTA is SAP's packaging format for deploying multiple interdependent applications and services as a single unit. Instead of deploying each component separately, you define everything in `mta.yaml` and deploy with one command.

### Why Use MTA?

1. **Single deployment unit**: Deploy frontend, backend, and services together
2. **Dependency management**: Services created before apps that need them
3. **Environment consistency**: Same deployment across dev/test/prod
4. **Rollback capability**: Undeploy entire stack at once

### MTA Structure

```
project/
├── mta.yaml           # Master descriptor
├── backend/
│   ├── manifest.yaml  # Optional: standalone deployment
│   └── ...
├── frontend/
│   └── ...
└── approuter/
    └── ...
```

### mta.yaml Anatomy

```yaml
_schema-version: "3.2"
ID: my-app
version: 1.0.0

# Global parameters
parameters:
  enable-parallel-deployments: true

# Your applications
modules:
  - name: my-backend
    type: python
    path: backend
    requires:
      - name: my-xsuaa    # Needs this service
    provides:
      - name: backend-api # Exposes this for others
        properties:
          url: ${default-url}

  - name: my-frontend
    type: html5
    path: frontend
    requires:
      - name: my-html5-host

# BTP services to create
resources:
  - name: my-xsuaa
    type: org.cloudfoundry.managed-service
    parameters:
      service: xsuaa
      service-plan: application
      path: xs-security.json
```

### Module Types

| Type | Description | Use Case |
|------|-------------|----------|
| `python` | Python buildpack app | FastAPI backend |
| `nodejs` | Node.js buildpack app | Express backend |
| `java` | Java buildpack app | Spring Boot |
| `html5` | Static content | SAPUI5/React frontend |
| `approuter.nodejs` | SAP App Router | Authentication gateway |
| `com.sap.application.content` | Content deployer | HTML5 repo deployment |

### Resource Types

| Type | Service | Use Case |
|------|---------|----------|
| `org.cloudfoundry.managed-service` | Any CF service | XSUAA, Destination, etc. |
| `org.cloudfoundry.user-provided-service` | Custom credentials | Azure secrets |
| `org.cloudfoundry.existing-service` | Pre-existing service | Shared services |

### Build and Deploy

```bash
# Install MTA Build Tool
npm install -g mbt

# Validate mta.yaml
mbt validate

# Build for Cloud Foundry
mbt build -p=cf

# Deploy
cf deploy mta_archives/my-app_1.0.0.mtar

# Undeploy (removes everything)
cf undeploy my-app --delete-services
```

---

## App Router Deep Dive

### What is App Router?

The App Router is a Node.js-based reverse proxy that:
1. Authenticates users via XSUAA
2. Routes requests to backend services
3. Serves static content from HTML5 repo
4. Manages user sessions

### Why Do You Need It?

```
WITHOUT App Router:
User → Frontend → Backend (each handles its own auth)
                → Other services

WITH App Router:
User → App Router → XSUAA (centralized auth)
            ↓
         Frontend
            ↓
         Backend (receives validated JWT)
```

### Request Flow

```
1. User accesses https://my-app.cfapps.eu10.hana.ondemand.com
2. App Router checks if user has valid session
3. If not, redirects to XSUAA login page
4. User authenticates (SAP IAS, Azure AD, etc.)
5. XSUAA redirects back with authorization code
6. App Router exchanges code for JWT token
7. App Router creates session, stores token
8. Request proceeds to frontend/backend with JWT
```

### xs-app.json Configuration

```json
{
  "authenticationMethod": "route",
  "welcomeFile": "/index.html",
  "logout": {
    "logoutEndpoint": "/logout",
    "logoutPage": "/"
  },
  "routes": [
    {
      "source": "^/api/(.*)$",
      "target": "/api/$1",
      "destination": "backend-dest",
      "authenticationType": "xsuaa",
      "csrfProtection": false
    },
    {
      "source": "^(.*)$",
      "target": "$1",
      "service": "html5-apps-repo-rt",
      "authenticationType": "xsuaa"
    }
  ]
}
```

### Route Properties

| Property | Description |
|----------|-------------|
| `source` | Regex pattern to match incoming requests |
| `target` | Path to forward to (can use capture groups) |
| `destination` | Name of destination (from Destination Service) |
| `service` | BTP service to route to (e.g., html5-apps-repo-rt) |
| `authenticationType` | `xsuaa`, `none`, or `basic` |
| `csrfProtection` | Enable/disable CSRF tokens |

### Environment Variables

```yaml
# In mta.yaml module properties
properties:
  TENANT_HOST_PATTERN: "^(.*)-${space}-my-app.${default-domain}"
  SESSION_TIMEOUT: 60
  CORS: '[{"uriPattern": "^/api/", "allowedOrigin": [{"host": "*"}]}]'
```

---

## XSUAA Authentication

### What is XSUAA?

XSUAA (Extended Services - User Account and Authentication) is SAP's OAuth2 authorization server. It:
- Issues JWT tokens after authentication
- Validates tokens on API requests
- Manages scopes (permissions) and roles

### OAuth2 Flow

```
┌────────┐                                    ┌────────┐
│  User  │                                    │ XSUAA  │
└───┬────┘                                    └───┬────┘
    │                                             │
    │  1. Access app                              │
    │──────────────────────────────────────────►  │
    │                                             │
    │  2. Redirect to login                       │
    │  ◄──────────────────────────────────────────│
    │                                             │
    │  3. User authenticates                      │
    │──────────────────────────────────────────►  │
    │                                             │
    │  4. Authorization code                      │
    │  ◄──────────────────────────────────────────│
    │                                             │
    │  5. Exchange code for tokens                │
    │──────────────────────────────────────────►  │
    │                                             │
    │  6. Access token (JWT) + Refresh token      │
    │  ◄──────────────────────────────────────────│
    │                                             │
```

### xs-security.json Explained

```json
{
  "xsappname": "my-app",
  "tenant-mode": "dedicated",
  
  "scopes": [
    {
      "name": "$XSAPPNAME.read",
      "description": "Read data"
    },
    {
      "name": "$XSAPPNAME.write",
      "description": "Write data"
    }
  ],
  
  "role-templates": [
    {
      "name": "Viewer",
      "scope-references": ["$XSAPPNAME.read"]
    },
    {
      "name": "Editor",
      "scope-references": ["$XSAPPNAME.read", "$XSAPPNAME.write"]
    }
  ],
  
  "role-collections": [
    {
      "name": "My App Viewer",
      "role-template-references": ["$XSAPPNAME.Viewer"]
    }
  ]
}
```

### JWT Token Structure

```json
{
  "sub": "user123",
  "email": "user@company.com",
  "given_name": "John",
  "family_name": "Doe",
  "scope": [
    "my-app!t12345.read",
    "my-app!t12345.write"
  ],
  "client_id": "sb-my-app!t12345",
  "zid": "tenant-id",
  "exp": 1704067200,
  "iat": 1704063600
}
```

### Validating JWT in Python

```python
import jwt
from jwt import PyJWKClient

def validate_token(token: str, xsuaa_url: str, client_id: str):
    """Validate XSUAA JWT token."""
    # Fetch public key from XSUAA
    jwks_client = PyJWKClient(f"{xsuaa_url}/token_keys")
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    
    # Decode and validate
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id
    )
    return payload
```

### Assigning Roles to Users

1. **BTP Cockpit** → Security → Role Collections
2. Find your role collection (e.g., "My App Viewer")
3. Click Edit → Add user email → Save

---

## Destination Service

### What is the Destination Service?

The Destination Service manages connections to external systems. Instead of hardcoding URLs and credentials in your app, you configure "destinations" in BTP Cockpit.

### Benefits

1. **Security**: Credentials not in code or env vars
2. **Flexibility**: Change endpoints without redeploying
3. **Multi-tenancy**: Different destinations per tenant
4. **Protocols**: HTTP, RFC, LDAP, Mail supported

### Creating a Destination (BTP Cockpit)

1. Go to **Connectivity** → **Destinations**
2. Click **New Destination**
3. Configure:

```
Name: AZURE_BLOB_STORAGE
Type: HTTP
URL: https://myaccount.blob.core.windows.net
Proxy Type: Internet
Authentication: NoAuthentication

Additional Properties:
  sap.cloud.service: ewa-analyzer
  URL.headers.x-ms-version: 2020-04-08
```

### Using Destinations in Code

```python
import requests
import os
import json

def get_destination_url(dest_name: str) -> dict:
    """Fetch destination details from Destination Service."""
    # Get Destination Service credentials from VCAP_SERVICES
    vcap = json.loads(os.getenv("VCAP_SERVICES", "{}"))
    dest_creds = vcap.get("destination", [{}])[0].get("credentials", {})
    
    # Get OAuth token for Destination Service
    token_url = f"{dest_creds['url']}/oauth/token"
    token_response = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": dest_creds["clientid"],
            "client_secret": dest_creds["clientsecret"]
        }
    )
    access_token = token_response.json()["access_token"]
    
    # Fetch destination configuration
    dest_url = f"{dest_creds['uri']}/destination-configuration/v1/destinations/{dest_name}"
    dest_response = requests.get(
        dest_url,
        headers={"Authorization": f"Bearer {access_token}"}
    )
    return dest_response.json()
```

### Destination in xs-app.json

```json
{
  "routes": [
    {
      "source": "^/api/(.*)$",
      "target": "$1",
      "destination": "backend-api",
      "authenticationType": "xsuaa"
    }
  ]
}
```

The App Router automatically resolves "backend-api" to the URL configured in Destination Service.

---

## HTML5 Application Repository

### What is It?

The HTML5 Application Repository is a managed service that:
- Stores static web content (HTML, JS, CSS)
- Serves content via App Router
- Provides versioning
- Handles caching/CDN

### Why Use It?

| Approach | Pros | Cons |
|----------|------|------|
| Nginx container | Full control | Manage container, scaling |
| HTML5 Repo | Zero ops, integrated | Less control |

### Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│                    MTA Deployment                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐    ┌─────────────────────┐   │
│  │  UI Deployer     │───►│  HTML5 App Repo     │   │
│  │  (one-time job)  │    │  (stores UI files)  │   │
│  └──────────────────┘    └──────────┬──────────┘   │
│                                      │              │
│                                      ▼              │
│                          ┌─────────────────────┐   │
│                          │  App Router         │   │
│                          │  (serves UI)        │   │
│                          └─────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### MTA Configuration

```yaml
modules:
  # UI5 application build
  - name: my-ui
    type: html5
    path: frontend
    build-parameters:
      builder: custom
      commands:
        - npm install
        - npm run build
      build-result: dist

  # Deployer (uploads to repo)
  - name: my-ui-deployer
    type: com.sap.application.content
    path: .
    requires:
      - name: my-html5-host
        parameters:
          content-target: true
    build-parameters:
      build-result: resources
      requires:
        - name: my-ui
          artifacts:
            - "*.zip"
          target-path: resources/

resources:
  # Host service (storage)
  - name: my-html5-host
    type: org.cloudfoundry.managed-service
    parameters:
      service: html5-apps-repo
      service-plan: app-host

  # Runtime service (serving)
  - name: my-html5-runtime
    type: org.cloudfoundry.managed-service
    parameters:
      service: html5-apps-repo
      service-plan: app-runtime
```

### Viewing Deployed Content

```bash
# Install HTML5 CLI plugin
cf install-plugin -r CF-Community "html5-plugin"

# List deployed apps
cf html5-list

# Get app info
cf html5-info my-ui
```

---

## Environment Variables & Service Bindings

### How CF Provides Configuration

When you bind a service to your app, CF injects credentials via environment variables:

```bash
# View all env vars
cf env my-app
```

### VCAP_SERVICES Structure

```json
{
  "xsuaa": [{
    "name": "my-xsuaa",
    "credentials": {
      "clientid": "sb-my-app!t12345",
      "clientsecret": "secret123",
      "url": "https://my-subdomain.authentication.eu10.hana.ondemand.com"
    }
  }],
  "destination": [{
    "name": "my-destination",
    "credentials": {
      "uri": "https://destination-configuration.cfapps.eu10.hana.ondemand.com",
      "clientid": "...",
      "clientsecret": "..."
    }
  }],
  "user-provided": [{
    "name": "my-azure-creds",
    "credentials": {
      "AZURE_STORAGE_CONNECTION_STRING": "...",
      "AZURE_OPENAI_API_KEY": "..."
    }
  }]
}
```

### VCAP_APPLICATION Structure

```json
{
  "application_name": "my-app",
  "application_id": "guid",
  "space_name": "dev",
  "organization_name": "my-org",
  "uris": ["my-app.cfapps.eu10.hana.ondemand.com"]
}
```

### Reading in Python

```python
import os
import json

def get_service_credentials(service_type: str, service_name: str = None) -> dict:
    """Get credentials from VCAP_SERVICES."""
    vcap = json.loads(os.getenv("VCAP_SERVICES", "{}"))
    services = vcap.get(service_type, [])
    
    if service_name:
        for svc in services:
            if svc.get("name") == service_name:
                return svc.get("credentials", {})
        return {}
    
    # Return first service of type
    return services[0].get("credentials", {}) if services else {}

# Usage
xsuaa_creds = get_service_credentials("xsuaa")
azure_creds = get_service_credentials("user-provided", "my-azure-creds")
```

### Setting Custom Environment Variables

```yaml
# In manifest.yaml
applications:
  - name: my-app
    env:
      MY_CUSTOM_VAR: "value"
      DEBUG: "false"
```

Or via CLI:
```bash
cf set-env my-app MY_CUSTOM_VAR "value"
cf restage my-app  # Required to pick up changes
```

---

## Summary

| Azure Concept | SAP BTP Equivalent |
|---------------|-------------------|
| Azure Web App | CF Application |
| App Service Plan | CF Memory/Instances |
| Azure Container Registry | Buildpacks |
| Azure Key Vault | User-Provided Services / Destination Service |
| Azure AD | XSUAA + SAP IAS |
| Azure Blob Storage | Object Store Service (or keep Azure via Destination) |
| Application Insights | CF Logging Service |
| Azure DevOps | SAP CI/CD Service / GitHub Actions |

The key mindset shift: In BTP, services are "bound" to apps, injecting configuration automatically. You don't manage infrastructure—you configure relationships in `mta.yaml`.
