# FinSync GCP Deployment Guide

## Quick Deploy

### Prerequisites
1. Install [gcloud CLI](https://cloud.google.com/sdk/docs/install)
2. Authenticate: `gcloud auth login`
3. Set project: `export GCP_PROJECT_ID=your-project-id`

### One-Command Deploy
```bash
./deploy.sh
```

The script will:
- Enable required GCP APIs
- Create Artifact Registry repo
- Create GCS bucket for uploads
- Set up Secret Manager
- Build Docker image
- Deploy to Cloud Run

---

## Manual Deployment

### 1. Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com
```

### 2. Create Artifact Registry
```bash
gcloud artifacts repositories create fin-sync-repo \
  --repository-format=docker \
  --location=us-central1
```

### 3. Create GCS Bucket
```bash
gcloud storage buckets create gs://YOUR_PROJECT_ID-finsync-uploads \
  --location=us-central1 \
  --uniform-bucket-level-access
```

### 4. Store Secrets
```bash
# Elastic credentials
echo "YOUR_ELASTIC_ENDPOINT" | gcloud secrets create ELASTIC_CLOUD_ENDPOINT --data-file=-
echo "YOUR_ELASTIC_API_KEY" | gcloud secrets create ELASTIC_API_KEY --data-file=-
```

### 5. Grant Secret Access to Cloud Run
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud secrets add-iam-policy-binding ELASTIC_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding ELASTIC_CLOUD_ENDPOINT \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 6. Deploy with Cloud Build
```bash
gcloud builds submit --config=cloudbuild.yaml
```

### 7. Deploy Directly (Alternative)
```bash
gcloud run deploy fin-sync \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars ENVIRONMENT=production,USE_SECRET_MANAGER=true \
  --set-secrets ELASTIC_API_KEY=ELASTIC_API_KEY:latest,ELASTIC_CLOUD_ENDPOINT=ELASTIC_CLOUD_ENDPOINT:latest
```

---

## Architecture

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Cloud Run      │  ← Streamlit App
│  (fin-sync)     │
└────┬─────┬──────┘
     │     │
     │     └──────────────┐
     │                    │
     ▼                    ▼
┌──────────────┐   ┌──────────────┐
│ Vertex AI    │   │  Elastic.co  │
│ - Gemini     │   │  - Search    │
│ - Embeddings │   │  - Analytics │
└──────────────┘   └──────────────┘
     │
     ▼
┌──────────────┐
│ Cloud        │
│ Storage      │  ← PDF uploads
│ (GCS)        │
└──────────────┘
```

## Cost Optimization

### 1. Cloud Run
- Min instances: 0 (scale to zero)
- Max instances: 10
- Auto-scaling based on concurrency

### 2. Storage
- GCS Standard class for uploads
- Enable lifecycle policies:
```bash
# Delete uploaded PDFs after 30 days
gcloud storage buckets update gs://YOUR_BUCKET \
  --lifecycle-file=lifecycle.json
```

**lifecycle.json:**
```json
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {"age": 30}
    }]
  }
}
```

### 3. Vertex AI
- Use `gemini-2.0-flash-exp` (faster, cheaper)
- Implement request caching
- Set rate limits

## Monitoring

### View Logs
```bash
gcloud run services logs read fin-sync --region=us-central1
```

### View Metrics
```bash
gcloud run services describe fin-sync --region=us-central1
```

### Set Up Alerts
- Go to Cloud Console → Monitoring → Alerting
- Create alerts for:
  - Error rate > 5%
  - Response latency > 10s
  - Memory usage > 80%

## Environment Variables

Production Cloud Run will have:
- `ENVIRONMENT=production`
- `USE_SECRET_MANAGER=true`
- `GCP_PROJECT_ID=<auto-set>`
- `PORT=8080`
- Secrets from Secret Manager

## Troubleshooting

### Build Fails
```bash
# Check Cloud Build logs
gcloud builds list --limit=5
gcloud builds log <BUILD_ID>
```

### Service Won't Start
```bash
# Check Cloud Run logs
gcloud run services logs read fin-sync --region=us-central1 --limit=50
```

### Permission Errors
```bash
# Grant Vertex AI access
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Grant GCS access
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

## CI/CD Setup

### Cloud Build Triggers
1. Go to Cloud Console → Cloud Build → Triggers
2. Create trigger:
   - Event: Push to branch
   - Branch: `^main$`
   - Config: `cloudbuild.yaml`
3. Every push to `main` auto-deploys

### GitHub Actions (Alternative)
Add `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud builds submit --config=cloudbuild.yaml
```

## Security Checklist

- ✅ Secrets in Secret Manager (not env vars)
- ✅ IAM roles with least privilege
- ✅ Cloud Run with authentication (if needed)
- ✅ VPC connector (optional, for private resources)
- ✅ HTTPS only (default on Cloud Run)
- ✅ Enable Cloud Armor (optional, for DDoS protection)

## Next Steps

1. Set up custom domain
2. Enable authentication (if needed)
3. Configure CDN (Cloud CDN)
4. Set up backup strategy for Elastic data
5. Implement request rate limiting

