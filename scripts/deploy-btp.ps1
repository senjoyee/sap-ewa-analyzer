# =============================================================================
# SAP BTP Deployment Script (PowerShell)
# =============================================================================
# This script deploys the EWA Analyzer to SAP BTP Cloud Foundry.
# 
# Prerequisites:
# 1. Cloud Foundry CLI installed (cf --version)
# 2. MTA Build Tool installed (mbt --version)
# 3. Logged into CF (cf login)
# 4. User-provided service created for Azure credentials
#
# Usage:
#   .\scripts\deploy-btp.ps1 [-SkipBuild] [-Space <space-name>]
# =============================================================================

param(
    [switch]$SkipBuild,
    [string]$Space = ""
)

$ErrorActionPreference = "Stop"

# Script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "========================================" -ForegroundColor Green
Write-Host "SAP BTP Deployment - EWA Analyzer" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Check prerequisites
Write-Host "`nChecking prerequisites..." -ForegroundColor Yellow

try {
    $cfVersion = cf version
    Write-Host "CF CLI: $cfVersion" -ForegroundColor Gray
} catch {
    Write-Host "Error: Cloud Foundry CLI not found. Install from https://github.com/cloudfoundry/cli/releases" -ForegroundColor Red
    exit 1
}

try {
    $mbtVersion = mbt --version
    Write-Host "MBT: $mbtVersion" -ForegroundColor Gray
} catch {
    Write-Host "Error: MTA Build Tool not found. Install with: npm install -g mbt" -ForegroundColor Red
    exit 1
}

# Check if logged in
try {
    cf target | Out-Null
} catch {
    Write-Host "Error: Not logged into Cloud Foundry. Run 'cf login' first." -ForegroundColor Red
    exit 1
}

# Switch space if specified
if ($Space -ne "") {
    Write-Host "Switching to space: $Space" -ForegroundColor Yellow
    cf target -s $Space
}

# Show current target
Write-Host "`nCurrent CF target:" -ForegroundColor Green
cf target

# Check for user-provided service
Write-Host "`nChecking for Azure credentials service..." -ForegroundColor Yellow
$serviceCheck = cf service ewa-analyzer-azure-credentials 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: User-provided service 'ewa-analyzer-azure-credentials' not found." -ForegroundColor Red
    Write-Host "Create it with:" -ForegroundColor Yellow
    Write-Host @"
cf cups ewa-analyzer-azure-credentials -p '{
  "AZURE_STORAGE_CONNECTION_STRING": "your-connection-string",
  "AZURE_STORAGE_CONTAINER_NAME": "ewa-analyzer",
  "AZURE_OPENAI_API_KEY": "your-api-key",
  "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
  "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
  "AZURE_OPENAI_SUMMARY_MODEL": "your-deployment-name"
}'
"@
    exit 1
}
Write-Host "Azure credentials service found." -ForegroundColor Green

# Build MTA archive
Set-Location $ProjectRoot

if (-not $SkipBuild) {
    Write-Host "`nBuilding MTA archive..." -ForegroundColor Yellow
    mbt build -p=cf
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: MTA build failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "MTA build completed." -ForegroundColor Green
} else {
    Write-Host "Skipping build (-SkipBuild flag set)" -ForegroundColor Yellow
}

# Find the MTA archive
$mtaArchive = Get-ChildItem -Path "mta_archives" -Filter "*.mtar" | Select-Object -First 1

if ($null -eq $mtaArchive) {
    Write-Host "Error: No MTA archive found in mta_archives/. Run without -SkipBuild." -ForegroundColor Red
    exit 1
}

Write-Host "`nDeploying MTA archive: $($mtaArchive.FullName)" -ForegroundColor Yellow

# Deploy
cf deploy $mtaArchive.FullName --retries 1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Show deployed apps
Write-Host "`nDeployed applications:" -ForegroundColor Yellow
cf apps | Select-String "ewa-analyzer"

# Get app URL
$appInfo = cf app ewa-analyzer-approuter
$routeLine = $appInfo | Select-String "routes:"
if ($routeLine) {
    $appUrl = ($routeLine -split '\s+')[1]
    Write-Host "`nApplication URL: https://$appUrl" -ForegroundColor Green
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Assign role collections to users in BTP Cockpit"
Write-Host "2. Configure destinations in BTP Cockpit (if needed)"
Write-Host "3. Test the application at the URL above"
