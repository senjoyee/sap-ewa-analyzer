# .github/scripts/deploy-local.ps1
# This script performs a manual build and deployment to SAP BTP Cloud Foundry.
# It assumes you are already logged in via 'cf8 login'.

$ErrorActionPreference = "Stop"

Write-Host "--- 1. Cleaning up old artifacts ---" -ForegroundColor Cyan
if (Test-Path "mta_archives") { Remove-Item -Recurse -Force "mta_archives" }
if (Test-Path "ewaanalyzer-1.0.0") { Remove-Item -Recurse -Force "ewaanalyzer-1.0.0" }

Write-Host "--- 2. Building MTA Archive (this may take a few minutes) ---" -ForegroundColor Cyan
mbt build -p=cf

Write-Host "--- 3. Deploying to SAP BTP ---" -ForegroundColor Cyan
# If you have a local mtaext.yaml for credentials, it will be used.
if (Test-Path "mtaext.yaml") {
    Write-Host "Using local mtaext.yaml for deployment..." -ForegroundColor Yellow
    cf8 deploy mta_archives/ewa-analyzer_1.0.0.mtar -e mtaext.yaml
} else {
    Write-Host "No mtaext.yaml found. Deploying with default configuration..." -ForegroundColor Yellow
    cf8 deploy mta_archives/ewa-analyzer_1.0.0.mtar
}

Write-Host "--- Deployment Complete! ---" -ForegroundColor Green
