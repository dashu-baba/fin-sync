#!/bin/bash
set -e

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID=${GCP_PROJECT_ID:-"your-gcp-project-id"}
REGION="us-central1"
REPO_NAME="fin-sync"
TRIGGER_NAME="fin-sync-auto-deploy"

echo -e "${GREEN}🔄 Setting up CI/CD for FinSync${NC}"
echo "=================================================="

# Connect to GitHub (interactive)
echo -e "\n${YELLOW}📦 Connecting to GitHub repository...${NC}"
echo "This will open a browser to authorize Cloud Build to access your GitHub repo."
read -p "Press Enter to continue..."

gcloud builds connections create github fin-sync-github \
    --project=$PROJECT_ID \
    --region=$REGION \
    2>/dev/null || echo "Connection already exists"

# List available repositories
echo -e "\n${YELLOW}Available repositories:${NC}"
gcloud builds repositories list --connection=fin-sync-github --region=$REGION --project=$PROJECT_ID 2>/dev/null || echo "No repositories connected yet"

# Create Cloud Build trigger
echo -e "\n${YELLOW}🔧 Creating Cloud Build trigger...${NC}"

gcloud builds triggers create github \
    --name=$TRIGGER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --repo-name=$REPO_NAME \
    --repo-owner=YOUR_GITHUB_USERNAME \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml \
    --substitutions=_SERVICE_NAME=fin-sync,_REGION=$REGION,_ARTIFACT_REPO=fin-sync-repo \
    2>&1 || echo "Trigger may already exist"

echo -e "\n${GREEN}=================================================="
echo -e "✅ CI/CD Setup Complete!"
echo -e "=================================================="
echo -e "Now when you push to 'main' branch:"
echo -e "  1. Cloud Build automatically builds Docker image"
echo -e "  2. Pushes to Artifact Registry"
echo -e "  3. Deploys to Cloud Run"
echo -e ""
echo -e "View triggers: https://console.cloud.google.com/cloud-build/triggers?project=$PROJECT_ID"
echo -e "==================================================${NC}"

