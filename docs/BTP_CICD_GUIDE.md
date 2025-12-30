# SAP BTP CI/CD Pipeline Guide

This guide explains how to set up continuous integration and deployment for SAP BTP Cloud Foundry.

## Overview

We provide two CI/CD options:

1. **GitHub Actions** (recommended) - Uses the workflow in `.github/workflows/deploy-to-btp.yml`
2. **SAP CI/CD Service** - Native BTP solution

## Option 1: GitHub Actions

### Prerequisites

1. GitHub repository with your code
2. SAP BTP account with Cloud Foundry enabled
3. Technical user for CI/CD (recommended over personal account)

### Required Secrets

Configure these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Description | Example |
|--------|-------------|---------|
| `CF_API_ENDPOINT` | Cloud Foundry API URL | `https://api.cf.eu10.hana.ondemand.com` |
| `CF_USERNAME` | BTP user email | `ci-user@company.com` |
| `CF_PASSWORD` | BTP password | (use service key or API token for SSO) |
| `CF_ORG` | CF Organization name | `my-org` |
| `CF_SPACE` | Default CF Space | `dev` |

**Optional secrets for automatic service creation:**

| Secret | Description |
|--------|-------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection |
| `AZURE_STORAGE_CONTAINER_NAME` | Container name |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_VERSION` | API version |
| `AZURE_OPENAI_SUMMARY_MODEL` | Model deployment name |

### Workflow File

The workflow is located at `.github/workflows/deploy-to-btp.yml` and includes:

```yaml
name: Deploy to SAP BTP

on:
  push:
    branches: [main, btp]
  workflow_dispatch:
    inputs:
      space:
        description: 'Target CF Space'
        type: choice
        options: [dev, test, prod]

jobs:
  build:
    # Builds MTA archive
    
  deploy:
    # Deploys to Cloud Foundry
    
  smoke-test:
    # Verifies deployment
```

### Manual Deployment

You can trigger a manual deployment:

1. Go to **Actions** tab in GitHub
2. Select **"Deploy to SAP BTP"** workflow
3. Click **"Run workflow"**
4. Choose target space (dev/test/prod)
5. Click **"Run workflow"** button

### Multi-Environment Setup

For separate dev/test/prod environments, create multiple CF Spaces and configure:

```yaml
# In workflow file
environment:
  name: ${{ github.event.inputs.space || 'dev' }}
```

Then in GitHub:
1. Go to **Settings → Environments**
2. Create environments: `dev`, `test`, `prod`
3. Add environment-specific secrets if needed
4. Configure required reviewers for `prod`

### Viewing Deployment Status

- **GitHub Actions** tab shows workflow runs
- Each deployment creates a **summary** with:
  - Application URL
  - Deployed apps status
  - Commit reference

---

## Option 2: SAP CI/CD Service

SAP's native CI/CD solution integrates directly with BTP.

### Setup Steps

1. **Enable SAP CI/CD Service** in BTP Cockpit:
   - Go to **Service Marketplace**
   - Find **"Continuous Integration & Delivery"**
   - Create instance

2. **Access CI/CD Application**:
   - Go to **Instances and Subscriptions**
   - Click on CI/CD application

3. **Add Repository**:
   - Click **Repositories** → **Add**
   - Connect to GitHub/GitLab/Bitbucket
   - Configure webhook

4. **Create Job**:
   - Click **Jobs** → **Create**
   - Select repository and branch
   - Choose pipeline: **"SAP Cloud Application Programming Model"** or **"MTA Build"**

5. **Configure Credentials**:
   - Add CF credentials in **Credentials** tab
   - Reference in job configuration

### SAP CI/CD Pipeline Configuration

Create `.pipeline/config.yml`:

```yaml
general:
  buildTool: mta

stages:
  Build:
    mtaBuild: true
    
  Integration:
    cloudFoundryDeploy:
      deployTool: mtaDeployPlugin
      cloudFoundry:
        org: my-org
        space: dev
        apiEndpoint: https://api.cf.eu10.hana.ondemand.com
        credentialsId: cf-credentials
```

---

## Best Practices

### 1. Use Technical Users

Don't use personal accounts for CI/CD. Create a technical user:

1. In SAP BTP Cockpit, go to **Security → Users**
2. Create a new user or use SAP Universal ID
3. Assign necessary role collections:
   - `Space Developer` (for deployment)
   - `Org Manager` (if creating services)

### 2. Protect Production

Configure branch protection and required reviews:

```yaml
# GitHub branch protection
on:
  push:
    branches: [main]
    
# Require approval for prod
environment:
  name: prod
  # GitHub environment with required reviewers
```

### 3. Version Your Deployments

Update `mta.yaml` version for tracking:

```yaml
# mta.yaml
version: 1.2.3  # Semantic versioning
```

Or use git tags:

```bash
git tag v1.2.3
git push origin v1.2.3
```

### 4. Rollback Strategy

If deployment fails:

```bash
# List previous versions
cf mta-ops

# View deployment history
cf dmol

# Rollback to previous version
cf undeploy ewa-analyzer
cf deploy previous-version.mtar
```

### 5. Blue-Green Deployment

For zero-downtime deployments:

```bash
cf deploy my-app.mtar --strategy blue-green
```

This:
1. Deploys new version alongside old
2. Routes traffic to new version
3. Keeps old version for quick rollback
4. Deletes old version after confirmation

---

## Troubleshooting CI/CD

### Build Fails

```bash
# Check MTA descriptor
mbt validate

# Test build locally
mbt build -p=cf
```

### Deployment Fails

Common issues:

1. **Service not found**: Create user-provided service first
2. **Insufficient memory**: Increase memory in manifest.yaml
3. **Buildpack error**: Check runtime.txt version
4. **Route conflict**: Delete old routes or use unique names

### View Deployment Logs

```bash
# In GitHub Actions, check workflow logs

# Or locally:
cf logs ewa-analyzer-backend --recent
cf events ewa-analyzer-backend
```

### Reset and Redeploy

```bash
# Remove everything
cf undeploy ewa-analyzer --delete-services --delete-service-keys

# Recreate Azure credentials service
cf cups ewa-analyzer-azure-credentials -p '{...}'

# Redeploy
cf deploy mta_archives/ewa-analyzer_1.0.0.mtar
```

---

## Security Considerations

1. **Never commit secrets** to repository
2. **Use GitHub encrypted secrets** for sensitive values
3. **Rotate credentials** regularly
4. **Audit access** to CI/CD systems
5. **Use service keys** instead of passwords where possible

### Creating CF Service Key

Instead of password authentication:

```bash
# Create service key
cf create-service-key my-xsuaa ci-cd-key

# Get credentials
cf service-key my-xsuaa ci-cd-key
```

Use the service key credentials in CI/CD.
