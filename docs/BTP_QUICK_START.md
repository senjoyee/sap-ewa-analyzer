# SAP BTP Quick Start Guide

This guide gets you from zero to deployed on SAP BTP in under 30 minutes.

## Prerequisites Checklist

- [ ] SAP BTP account with Cloud Foundry enabled
- [ ] Cloud Foundry CLI installed
- [ ] MTA Build Tool installed
- [ ] Your Azure credentials ready

## Step 1: Install Tools (5 minutes)

### Cloud Foundry CLI

```powershell
# Windows (Chocolatey)
choco install cloudfoundry-cli

# Or download from: https://github.com/cloudfoundry/cli/releases
```

### MTA Build Tool

```powershell
npm install -g mbt
```

### Verify Installation

```powershell
cf version    # Should show v8.x or higher
mbt --version # Should show 1.x
```

## Step 2: Login to SAP BTP (2 minutes)

```powershell
# Get your API endpoint from BTP Cockpit > Cloud Foundry > API Endpoint
cf login -a https://api.cf.eu10.hana.ondemand.com

# Enter your email and password when prompted
# Select your org and space
```

**Finding your API endpoint:**
1. Open SAP BTP Cockpit
2. Go to your Subaccount
3. Click "Cloud Foundry Environment"
4. Copy the "API Endpoint" URL

## Step 3: Create Azure Credentials Service (3 minutes)

Create a user-provided service with your Azure credentials:

```powershell
cf cups ewa-analyzer-azure-credentials -p '{
  "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;EndpointSuffix=core.windows.net",
  "AZURE_STORAGE_CONTAINER_NAME": "ewa-analyzer",
  "AZURE_OPENAI_API_KEY": "your-api-key-here",
  "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
  "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
  "AZURE_OPENAI_SUMMARY_MODEL": "gpt-5"
}'
```

**Tip:** If you need to update credentials later:
```powershell
cf uups ewa-analyzer-azure-credentials -p '{"key": "new-value"}'
```

## Step 4: Build the Application (5 minutes)

```powershell
cd c:\GenAI\ewa_analyzer

# Build the MTA archive
mbt build -p=cf
```

This creates `mta_archives/ewa-analyzer_1.0.0.mtar`.

## Step 5: Deploy to BTP (10 minutes)

```powershell
# Deploy the MTA archive
cf deploy mta_archives/ewa-analyzer_1.0.0.mtar
```

Watch the output for any errors. The deployment:
1. Creates XSUAA service instance
2. Creates Destination service instance
3. Creates HTML5 repo instances
4. Deploys backend application
5. Deploys frontend to HTML5 repo
6. Deploys App Router

## Step 6: Assign Role Collections (2 minutes)

1. Open **SAP BTP Cockpit**
2. Go to **Security** → **Role Collections**
3. Find **"EWA Analyzer Analyst"**
4. Click **Edit**
5. Add your user email under **Users**
6. Save

## Step 7: Access Your Application

```powershell
# Get the application URL
cf app ewa-analyzer-approuter
```

Look for the `routes:` line. Your app is at `https://<route>`.

## Troubleshooting

### "Service not found" during deployment

```powershell
# Check if the Azure credentials service exists
cf services

# If not, create it (Step 3)
```

### "Unauthorized" when accessing the app

1. Check role collection assignment (Step 6)
2. Try logging out and back in
3. Clear browser cache

### Backend not responding

```powershell
# Check backend status
cf app ewa-analyzer-backend

# View recent logs
cf logs ewa-analyzer-backend --recent
```

### Build fails

```powershell
# Validate mta.yaml
mbt validate

# Check Node.js version (need 18+)
node --version
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `cf login` | Login to Cloud Foundry |
| `cf target` | Show current org/space |
| `cf apps` | List deployed apps |
| `cf services` | List service instances |
| `cf logs <app> --recent` | View recent logs |
| `cf restart <app>` | Restart an app |
| `cf delete <app>` | Delete an app |
| `cf deploy <mtar>` | Deploy MTA archive |

## Next Steps

- Read the full [Migration Guide](SAP_BTP_MIGRATION_GUIDE.md)
- Set up [CI/CD Pipeline](BTP_CICD_GUIDE.md)
- Configure [Custom Domain](https://help.sap.com/docs/custom-domain)
- Integrate with [SAP Build Work Zone](https://help.sap.com/docs/build-work-zone-standard-edition)
