# .github/scripts/deploy-local.ps1
# This script performs a manual build and deployment to SAP BTP Cloud Foundry.
# It assumes you are already logged in via 'cf8 login'.

$ErrorActionPreference = "Stop"

Write-Host "--- 1. Cleaning up old artifacts ---" -ForegroundColor Cyan
if (Test-Path "mta_archives") { Remove-Item -Recurse -Force "mta_archives" }
if (Test-Path "sapui5/dist") { Remove-Item -Recurse -Force "sapui5/dist" }
if (Test-Path "ui-deployer/resources") { Remove-Item -Recurse -Force "ui-deployer/resources" }

Write-Host "--- 2. Building MTA Archive (this may take a few minutes) ---" -ForegroundColor Cyan
# We specify the mtar name to avoid versioning issues in the deployment step
mbt build -t ./mta_archives --mtar ewa_analyzer.mtar

Write-Host "--- 3. Deploying to SAP BTP ---" -ForegroundColor Cyan
# If you have a local mtaext.yaml for credentials, it will be used.
$params = @("deploy", "mta_archives/ewa_analyzer.mtar", "-f")
if (Test-Path "mtaext.yaml") {
    Write-Host "Using local mtaext.yaml for deployment..." -ForegroundColor Yellow
    $params += "-e"
    $params += "mtaext.yaml"
} else {
    Write-Host "No mtaext.yaml found. Deploying with default configuration..." -ForegroundColor Yellow
}

Write-Host "Executing: cf8 $params" -ForegroundColor DarkGray
cf8 $params

Write-Host "--- Deployment Complete! ---" -ForegroundColor Green
