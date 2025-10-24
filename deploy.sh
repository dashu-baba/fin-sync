#!/bin/bash
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-""}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="fin-sync"
ARTIFACT_REPO="fin-sync-repo"

echo -e "${GREEN}🚀 FinSync GCP Deployment Script${NC}"
echo "=================================================="

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check if project ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}📝 GCP_PROJECT_ID not set. Please enter your project ID:${NC}"
    read -r PROJECT_ID
fi

echo -e "${GREEN}✓ Using Project: ${PROJECT_ID}${NC}"
echo -e "${GREEN}✓ Region: ${REGION}${NC}"

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo -e "\n${YELLOW}🔧 Enabling required GCP APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com

# Create Artifact Registry repository
echo -e "\n${YELLOW}📦 Creating Artifact Registry repository...${NC}"
gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Docker repository for FinSync" \
    2>/dev/null || echo "Repository already exists"

# Create GCS bucket for file uploads
echo -e "\n${YELLOW}🪣 Creating GCS bucket for uploads...${NC}"
BUCKET_NAME="finsync-user-uploads"
gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    2>/dev/null || echo "Bucket already exists"

# Grant Cloud Run service account access to bucket
echo -e "\n${YELLOW}🔑 Granting Cloud Run service account access to bucket...${NC}"
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
gsutil iam ch "serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectAdmin" "gs://${BUCKET_NAME}" \
    2>/dev/null || echo "Permissions already set"

# Create secrets (if not exist)
echo -e "\n${YELLOW}🔐 Setting up Secret Manager...${NC}"
echo "Please enter your Elastic Cloud Endpoint (or press Enter to skip):"
read -r ELASTIC_ENDPOINT
if [ -n "$ELASTIC_ENDPOINT" ]; then
    echo "$ELASTIC_ENDPOINT" | gcloud secrets create ELASTIC_CLOUD_ENDPOINT \
        --data-file=- 2>/dev/null || \
    echo "$ELASTIC_ENDPOINT" | gcloud secrets versions add ELASTIC_CLOUD_ENDPOINT \
        --data-file=-
fi

echo "Please enter your Elastic API Key (or press Enter to skip):"
read -rs ELASTIC_KEY
if [ -n "$ELASTIC_KEY" ]; then
    echo "$ELASTIC_KEY" | gcloud secrets create ELASTIC_API_KEY \
        --data-file=- 2>/dev/null || \
    echo "$ELASTIC_KEY" | gcloud secrets versions add ELASTIC_API_KEY \
        --data-file=-
fi

# Build and deploy using Cloud Build
echo -e "\n${YELLOW}🏗️  Building and deploying with Cloud Build...${NC}"
gcloud builds submit --config=cloudbuild.yaml \
    --substitutions=_SERVICE_NAME="$SERVICE_NAME",_REGION="$REGION",_ARTIFACT_REPO="$ARTIFACT_REPO"

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format="value(status.url)")

echo -e "\n${GREEN}=================================================="
echo -e "✅ Deployment Complete!"
echo -e "=================================================="
echo -e "Service URL: ${SERVICE_URL}"
echo -e "Project: ${PROJECT_ID}"
echo -e "Region: ${REGION}"
echo -e "Bucket: gs://${BUCKET_NAME}"
echo -e "==================================================${NC}"

