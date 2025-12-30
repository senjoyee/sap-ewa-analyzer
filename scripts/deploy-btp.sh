#!/bin/bash
# =============================================================================
# SAP BTP Deployment Script
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
#   ./scripts/deploy-btp.sh [--skip-build] [--space <space-name>]
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
SKIP_BUILD=false
TARGET_SPACE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --space)
            TARGET_SPACE="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SAP BTP Deployment - EWA Analyzer${NC}"
echo -e "${GREEN}========================================${NC}"

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v cf &> /dev/null; then
    echo -e "${RED}Error: Cloud Foundry CLI not found. Install from https://github.com/cloudfoundry/cli/releases${NC}"
    exit 1
fi

if ! command -v mbt &> /dev/null; then
    echo -e "${RED}Error: MTA Build Tool not found. Install with: npm install -g mbt${NC}"
    exit 1
fi

# Check if logged in
if ! cf target &> /dev/null; then
    echo -e "${RED}Error: Not logged into Cloud Foundry. Run 'cf login' first.${NC}"
    exit 1
fi

# Switch space if specified
if [ -n "$TARGET_SPACE" ]; then
    echo -e "${YELLOW}Switching to space: $TARGET_SPACE${NC}"
    cf target -s "$TARGET_SPACE"
fi

# Show current target
echo -e "${GREEN}Current CF target:${NC}"
cf target

# Check for user-provided service
echo -e "\n${YELLOW}Checking for Azure credentials service...${NC}"
if ! cf service ewa-analyzer-azure-credentials &> /dev/null; then
    echo -e "${RED}Error: User-provided service 'ewa-analyzer-azure-credentials' not found.${NC}"
    echo -e "${YELLOW}Create it with:${NC}"
    echo -e "cf cups ewa-analyzer-azure-credentials -p '{
  \"AZURE_STORAGE_CONNECTION_STRING\": \"your-connection-string\",
  \"AZURE_STORAGE_CONTAINER_NAME\": \"ewa-analyzer\",
  \"AZURE_OPENAI_API_KEY\": \"your-api-key\",
  \"AZURE_OPENAI_ENDPOINT\": \"https://your-resource.openai.azure.com/\",
  \"AZURE_OPENAI_API_VERSION\": \"2024-12-01-preview\",
  \"AZURE_OPENAI_SUMMARY_MODEL\": \"your-deployment-name\"
}'"
    exit 1
fi
echo -e "${GREEN}Azure credentials service found.${NC}"

# Build MTA archive
cd "$PROJECT_ROOT"

if [ "$SKIP_BUILD" = false ]; then
    echo -e "\n${YELLOW}Building MTA archive...${NC}"
    mbt build -p=cf
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: MTA build failed.${NC}"
        exit 1
    fi
    echo -e "${GREEN}MTA build completed.${NC}"
else
    echo -e "${YELLOW}Skipping build (--skip-build flag set)${NC}"
fi

# Find the MTA archive
MTA_ARCHIVE=$(find mta_archives -name "*.mtar" -type f | head -1)

if [ -z "$MTA_ARCHIVE" ]; then
    echo -e "${RED}Error: No MTA archive found in mta_archives/. Run without --skip-build.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Deploying MTA archive: $MTA_ARCHIVE${NC}"

# Deploy
cf deploy "$MTA_ARCHIVE" --retries 1

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Deployment failed.${NC}"
    exit 1
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"

# Show deployed apps
echo -e "\n${YELLOW}Deployed applications:${NC}"
cf apps | grep ewa-analyzer

# Get app URL
APP_URL=$(cf app ewa-analyzer-approuter | grep "routes:" | awk '{print $2}')
echo -e "\n${GREEN}Application URL: https://$APP_URL${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Assign role collections to users in BTP Cockpit"
echo "2. Configure destinations in BTP Cockpit (if needed)"
echo "3. Test the application at the URL above"
