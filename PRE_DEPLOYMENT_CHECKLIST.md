# Pre-Deployment Checklist

## ✅ Before Deploying

### 1. Verify Environment Variables

Make sure you have these set in your terminal:

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="us-central1"  # optional, defaults to us-central1
```

### 2. Verify GCP Prerequisites

- [ ] Google Cloud SDK installed (`gcloud --version`)
- [ ] Authenticated to GCP (`gcloud auth login`)
- [ ] Billing enabled on your project
- [ ] Project ID is correct

### 3. Required GCP APIs

The deployment script will enable these automatically:
- Cloud Run API
- Cloud Build API
- Artifact Registry API
- Secret Manager API
- Cloud Storage API
- Vertex AI API

### 4. Prepare Secrets

You'll be prompted during deployment for:
- **Elastic Cloud Endpoint** - Your Elasticsearch endpoint URL
- **Elastic API Key** - Your Elasticsearch API key

Have these ready!

### 5. Check Current Deployment (if updating)

```bash
gcloud run services list --region=us-central1
```

## 🚀 Deployment Commands

### Option 1: Full Automated Deployment

```bash
# Set your project ID
export GCP_PROJECT_ID="your-gcp-project-id"

# Run deployment script
./deploy.sh
```

This will:
1. ✅ Enable required APIs
2. ✅ Create Artifact Registry
3. ✅ Create GCS bucket for uploads
4. ✅ Set up Secret Manager
5. ✅ Grant permissions to Cloud Run service account
6. ✅ Build Docker image
7. ✅ Deploy to Cloud Run

### Option 2: Manual Step-by-Step

If you prefer more control:

```bash
# 1. Set project
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID

# 2. Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  storage.googleapis.com aiplatform.googleapis.com

# 3. Create bucket
gsutil mb -p $GCP_PROJECT_ID -l us-central1 \
  gs://${GCP_PROJECT_ID}-finsync-uploads

# 4. Grant permissions
gsutil iam ch serviceAccount:${GCP_PROJECT_ID}@appspot.gserviceaccount.com:roles/storage.objectAdmin \
  gs://${GCP_PROJECT_ID}-finsync-uploads

# 5. Create secrets
echo "YOUR_ELASTIC_ENDPOINT" | gcloud secrets create ELASTIC_CLOUD_ENDPOINT --data-file=-
echo "YOUR_ELASTIC_KEY" | gcloud secrets create ELASTIC_API_KEY --data-file=-

# 6. Build and deploy
gcloud builds submit --config=cloudbuild.yaml
```

## 📊 What Gets Deployed

### Environment Variables Set
```
ENVIRONMENT=production
GCP_PROJECT_ID=<your-project>
GCS_BUCKET=<your-project>-finsync-uploads
VERTEX_MODEL_EMBED=text-embedding-004
USE_SECRET_MANAGER=true
```

### Secrets Loaded from Secret Manager
```
ELASTIC_CLOUD_ENDPOINT (from Secret Manager)
ELASTIC_API_KEY (from Secret Manager)
```

### Cloud Run Configuration
- **Memory**: 2Gi
- **CPU**: 2
- **Timeout**: 300s
- **Max Instances**: 10
- **Min Instances**: 0 (scales to zero)
- **Authentication**: Allow unauthenticated

### GCS Bucket
- **Name**: `<project-id>-finsync-uploads`
- **Location**: us-central1
- **Access**: Uniform bucket-level access
- **Permissions**: Cloud Run service account has objectAdmin role

## 🔍 Post-Deployment Verification

### 1. Check Service Status

```bash
gcloud run services describe fin-sync --region=us-central1
```

### 2. Get Service URL

```bash
gcloud run services describe fin-sync \
  --region=us-central1 \
  --format="value(status.url)"
```

### 3. Check Logs

```bash
# Real-time logs
gcloud run services logs tail fin-sync --region=us-central1

# Recent logs
gcloud run services logs read fin-sync --limit=50 --region=us-central1
```

### 4. Test the Application

```bash
# Get URL
SERVICE_URL=$(gcloud run services describe fin-sync \
  --region=us-central1 \
  --format="value(status.url)")

# Test health endpoint
curl -I ${SERVICE_URL}/_stcore/health
```

### 5. Verify Storage Mode

Check the logs after first upload:
```bash
gcloud run services logs read fin-sync --limit=100 | grep "storage backend"
```

Should see:
```
INFO | Using GCS storage backend
INFO | Upload mode: storage backend (GCS)
```

### 6. Verify GCS Bucket Access

```bash
# List files in bucket (should be empty initially)
gsutil ls gs://${GCP_PROJECT_ID}-finsync-uploads/

# Check bucket permissions
gsutil iam get gs://${GCP_PROJECT_ID}-finsync-uploads/
```

## 🐛 Troubleshooting

### Issue: "Permission denied" during deployment

**Solution**: Ensure you're authenticated and have proper roles
```bash
gcloud auth login
gcloud auth application-default login
```

### Issue: "API not enabled"

**Solution**: Enable required APIs
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

### Issue: Files saving locally in production

**Cause**: GCS_BUCKET environment variable not set

**Check**:
```bash
gcloud run services describe fin-sync \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"
```

Should include: `GCS_BUCKET=<project>-finsync-uploads`

### Issue: "Bucket does not exist"

**Solution**: Create the bucket
```bash
gsutil mb gs://${GCP_PROJECT_ID}-finsync-uploads
```

### Issue: Cloud Run can't access bucket

**Solution**: Grant permissions
```bash
gsutil iam ch serviceAccount:${GCP_PROJECT_ID}@appspot.gserviceaccount.com:roles/storage.objectAdmin \
  gs://${GCP_PROJECT_ID}-finsync-uploads
```

## 📋 New Features in This Deployment

### ✨ Duplicate Upload Protection
- Filename checking
- Content hash checking (SHA-256)
- Elasticsearch metadata checking
- Works with both local and GCS storage

### ☁️ Storage Backend Switching
- **Development**: Uses local filesystem (`data/uploads/`)
- **Production**: Uses GCS bucket (automatic)
- Duplicate detection works with both backends
- Single codebase for all environments

### 🔄 What Changed from Previous Deployment

1. **cloudbuild.yaml**:
   - Added `GCS_BUCKET` environment variable
   - Added `USE_SECRET_MANAGER=true`

2. **deploy.sh**:
   - Added GCS bucket permission grant for Cloud Run service account

3. **Application Code**:
   - Enhanced upload service with duplicate detection
   - Storage backend auto-detection
   - GCS integration for production

## 💰 Cost Estimate

| Service | Usage | Est. Monthly Cost |
|---------|-------|-------------------|
| Cloud Run | 10K requests, 2Gi mem | ~$5 |
| Cloud Build | 10 builds | ~$1 |
| GCS Storage | 10GB | $0.20 |
| Artifact Registry | 5GB | $0.50 |
| Secret Manager | 3 secrets | $0.18 |
| Vertex AI | 1M tokens | $10-20 |
| **Total** | | **~$17-27/mo** |

*Cloud Run scales to zero when not in use, so actual costs may be lower.*

## 🔒 Security Notes

- ✅ Secrets stored in Secret Manager (not in code)
- ✅ GCS bucket has uniform bucket-level access
- ✅ Cloud Run uses least-privilege service account
- ✅ All traffic over HTTPS
- ✅ Container runs as non-root user
- ✅ Duplicate detection prevents data integrity issues

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GCS Documentation](https://cloud.google.com/storage/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Storage Backend Implementation](docs/STORAGE_BACKEND_IMPLEMENTATION.md)
- [Duplicate Protection](docs/DUPLICATE_PROTECTION.md)

## ✅ Ready to Deploy?

If you've completed the checklist above, run:

```bash
export GCP_PROJECT_ID="your-project-id"
./deploy.sh
```

The script will guide you through the rest! 🚀

