# SAP BTP Troubleshooting Guide

Common issues and solutions when deploying to SAP BTP Cloud Foundry.

## Quick Diagnostics

```bash
# Check app status
cf apps

# View recent logs
cf logs ewa-analyzer-backend --recent

# Check service bindings
cf services

# View app environment
cf env ewa-analyzer-backend

# Check app events
cf events ewa-analyzer-backend
```

---

## Build Issues

### Issue: MTA build fails with "command not found"

**Symptom:**
```
Error: npm: command not found
```

**Solution:**
Ensure Node.js is installed and in PATH:
```bash
node --version  # Should be 18+
npm --version
```

### Issue: MTA build fails with schema validation error

**Symptom:**
```
Error: Validation of mta.yaml failed
```

**Solution:**
```bash
# Validate mta.yaml
mbt validate

# Common fixes:
# - Check indentation (YAML is indent-sensitive)
# - Ensure all referenced paths exist
# - Verify resource names match module requires
```

### Issue: UI5 build fails

**Symptom:**
```
Error: Could not find ui5.yaml
```

**Solution:**
Ensure `ui5.yaml` exists in the sapui5 directory:
```yaml
specVersion: "3.0"
metadata:
  name: ewa.analyzer
type: application
```

---

## Deployment Issues

### Issue: "Service not found" during deployment

**Symptom:**
```
Error: Service instance 'ewa-analyzer-azure-credentials' not found
```

**Solution:**
Create the user-provided service before deployment:
```bash
cf cups ewa-analyzer-azure-credentials -p '{
  "AZURE_STORAGE_CONNECTION_STRING": "...",
  "AZURE_STORAGE_CONTAINER_NAME": "...",
  "AZURE_OPENAI_API_KEY": "...",
  "AZURE_OPENAI_ENDPOINT": "...",
  "AZURE_OPENAI_API_VERSION": "...",
  "AZURE_OPENAI_SUMMARY_MODEL": "..."
}'
```

### Issue: "Insufficient memory" error

**Symptom:**
```
Error: App instance exited with insufficient memory
```

**Solution:**
Increase memory in `backend/manifest.yaml`:
```yaml
applications:
  - name: ewa-analyzer-backend
    memory: 1024M  # Increase to 2048M if needed
```

### Issue: "Route already exists" error

**Symptom:**
```
Error: The route ewa-analyzer-dev.cfapps.eu10.hana.ondemand.com is already in use
```

**Solution:**
```bash
# Option 1: Delete the existing route
cf delete-route cfapps.eu10.hana.ondemand.com --hostname ewa-analyzer-dev

# Option 2: Use a unique hostname in mta.yaml
parameters:
  routes:
    - route: ewa-analyzer-${timestamp}-${space}.${default-domain}
```

### Issue: Buildpack detection fails

**Symptom:**
```
Error: Unable to detect buildpack
```

**Solution:**
Ensure `runtime.txt` exists in backend/:
```
python-3.12.x
```

And `Procfile` specifies the start command:
```
web: gunicorn ewa_main:app -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT
```

---

## Runtime Issues

### Issue: App crashes on startup

**Symptom:**
```
App instance exited
```

**Diagnosis:**
```bash
cf logs ewa-analyzer-backend --recent
```

**Common causes:**
1. Missing environment variables
2. Service binding failed
3. Port binding issue

**Solutions:**
```bash
# Check environment
cf env ewa-analyzer-backend

# Check service binding
cf services

# Verify PORT usage in code
# Must use: port = int(os.getenv("PORT", "8001"))
```

### Issue: "502 Bad Gateway" from App Router

**Symptom:**
Frontend loads but API calls fail with 502

**Diagnosis:**
```bash
# Check backend is running
cf app ewa-analyzer-backend

# Check App Router logs
cf logs ewa-analyzer-approuter --recent
```

**Solutions:**
1. Verify backend health endpoint works:
   ```bash
   curl https://ewa-analyzer-backend.cfapps.eu10.hana.ondemand.com/health
   ```

2. Check destination configuration in `xs-app.json`:
   ```json
   {
     "routes": [{
       "source": "^/api/(.*)$",
       "destination": "ewa-backend"
     }]
   }
   ```

3. Verify destination exists in BTP Cockpit or mta.yaml

### Issue: "401 Unauthorized" on API calls

**Symptom:**
API calls return 401 even after login

**Diagnosis:**
```bash
# Check XSUAA binding
cf env ewa-analyzer-approuter | grep xsuaa
```

**Solutions:**
1. Verify XSUAA service is bound to App Router
2. Check xs-app.json has correct authenticationType:
   ```json
   {
     "authenticationType": "xsuaa"
   }
   ```
3. Ensure user has role collection assigned in BTP Cockpit

### Issue: "403 Forbidden" on API calls

**Symptom:**
User is authenticated but gets 403

**Solutions:**
1. Check user has required role collection:
   - BTP Cockpit → Security → Role Collections
   - Find "EWA Analyzer Analyst"
   - Verify user is assigned

2. Check scope in xs-security.json matches what backend expects

### Issue: Azure Blob Storage connection fails

**Symptom:**
```
Error: Azure Blob Service client not initialized
```

**Diagnosis:**
```bash
cf env ewa-analyzer-backend | grep AZURE
```

**Solutions:**
1. Update user-provided service with correct credentials:
   ```bash
   cf uups ewa-analyzer-azure-credentials -p '{
     "AZURE_STORAGE_CONNECTION_STRING": "correct-connection-string"
   }'
   ```

2. Restage the app to pick up changes:
   ```bash
   cf restage ewa-analyzer-backend
   ```

### Issue: Azure OpenAI calls fail

**Symptom:**
```
Error: DeploymentNotFound
```

**Solutions:**
1. Verify deployment name matches Azure OpenAI:
   ```bash
   cf env ewa-analyzer-backend | grep OPENAI
   ```

2. Update if incorrect:
   ```bash
   cf uups ewa-analyzer-azure-credentials -p '{
     "AZURE_OPENAI_SUMMARY_MODEL": "correct-deployment-name"
   }'
   cf restage ewa-analyzer-backend
   ```

---

## Performance Issues

### Issue: App is slow to respond

**Diagnosis:**
```bash
# Check app metrics
cf app ewa-analyzer-backend

# View CPU/memory usage
cf ssh ewa-analyzer-backend -c "ps aux"
```

**Solutions:**
1. Increase instances:
   ```bash
   cf scale ewa-analyzer-backend -i 2
   ```

2. Increase memory:
   ```bash
   cf scale ewa-analyzer-backend -m 2G
   ```

3. Enable auto-scaling (requires SAP Application Autoscaler service)

### Issue: Cold start takes too long

**Symptom:**
First request after idle period is slow

**Solutions:**
1. Increase instances to keep at least one warm
2. Configure health check to prevent premature restarts:
   ```yaml
   health-check-invocation-timeout: 120
   ```

---

## Logging and Monitoring

### Enable Debug Logging

```bash
cf set-env ewa-analyzer-backend DEBUG "true"
cf restage ewa-analyzer-backend
```

### Stream Logs

```bash
# Real-time logs
cf logs ewa-analyzer-backend

# Filter by type
cf logs ewa-analyzer-backend | grep ERROR
```

### Export Logs

```bash
# Recent logs to file
cf logs ewa-analyzer-backend --recent > backend-logs.txt
```

---

## Recovery Procedures

### Full Redeployment

```bash
# 1. Undeploy everything
cf undeploy ewa-analyzer --delete-services --delete-service-keys

# 2. Recreate Azure credentials
cf cups ewa-analyzer-azure-credentials -p '{...}'

# 3. Rebuild and deploy
mbt build -p=cf
cf deploy mta_archives/ewa-analyzer_1.0.0.mtar
```

### Rollback to Previous Version

```bash
# View deployment history
cf mta-ops

# If you have the previous .mtar file:
cf deploy previous-version.mtar
```

### Reset User-Provided Service

```bash
# Delete and recreate
cf delete-service ewa-analyzer-azure-credentials -f
cf cups ewa-analyzer-azure-credentials -p '{...}'
cf restage ewa-analyzer-backend
```

---

## Getting Help

1. **SAP Community**: https://community.sap.com
2. **SAP Support**: Via SAP ONE Support Launchpad
3. **Cloud Foundry Docs**: https://docs.cloudfoundry.org
4. **BTP Documentation**: https://help.sap.com/btp
