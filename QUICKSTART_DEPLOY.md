# FinSync - Quick Deploy to GCP

## ✅ What's Been Implemented

### Files Created:
1. **`Dockerfile`** - Containerizes Streamlit app
2. **`cloudbuild.yaml`** - Automated Cloud Build config
3. **`.dockerignore`** - Optimizes Docker builds
4. **`.env.example`** - Environment variable template
5. **`deploy.sh`** - One-click deployment script
6. **`core/storage.py`** - GCS/Local storage abstraction
7. **`core/secrets.py`** - Secret Manager integration
8. **`DEPLOYMENT.md`** - Complete deployment guide

### Code Updated:
- **`requirements.txt`** - Added `google-cloud-secret-manager`
- **`core/config.py`** - Integrated Secret Manager support

---

## 🚀 Deploy in 3 Steps

### Step 1: Setup GCP Project
```bash
# Install gcloud CLI (if not installed)
# Mac: brew install --cask google-cloud-sdk
# Or: https://cloud.google.com/sdk/docs/install

# Login and set project
gcloud auth login
export GCP_PROJECT_ID="your-project-id"
```

### Step 2: Prepare Credentials
Copy `.env.example` to `.env` and fill in:
```bash
cp .env.example .env
```

Edit `.env` with your values:
- `GCP_PROJECT_ID`
- `GCS_BUCKET` (will be created)
- `ELASTIC_CLOUD_ENDPOINT`
- `ELASTIC_API_KEY`

### Step 3: Deploy
```bash
./deploy.sh
```

That's it! ✨

---

## 📋 What Happens During Deployment

1. **Enables GCP APIs**: Cloud Run, Build, Storage, Vertex AI, Secret Manager
2. **Creates Artifact Registry**: Stores Docker images
3. **Creates GCS Bucket**: For PDF uploads (`gs://PROJECT_ID-finsync-uploads`)
4. **Stores Secrets**: Elastic credentials in Secret Manager
5. **Builds Docker Image**: From your code
6. **Deploys to Cloud Run**: Auto-scaling, HTTPS, serverless

---

## 🔧 Manual Deploy (Alternative)

```bash
# Quick deploy without script
gcloud run deploy fin-sync \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars ENVIRONMENT=production,GCP_PROJECT_ID=$(gcloud config get-value project)
```

---

## 🏗️ Architecture Overview

**Services Used:**
- **Cloud Run**: Hosts Streamlit app (auto-scales 0-10 instances)
- **Cloud Storage**: Stores uploaded PDFs
- **Secret Manager**: Secures API keys
- **Vertex AI**: Gemini for parsing & chat
- **Elastic Cloud**: Search & analytics (external)

**Cost**: ~$20-50/month for moderate usage
- Cloud Run: Pay-per-use, scales to zero
- Storage: ~$0.02/GB/month
- Vertex AI: ~$0.00025/1K chars (Gemini Flash)

---

## 📝 Environment Modes

### Development (Local)
```bash
ENVIRONMENT=development
USE_SECRET_MANAGER=false
# Uses local data/uploads/ directory
# Reads from .env file
```

### Production (Cloud Run)
```bash
ENVIRONMENT=production
USE_SECRET_MANAGER=true
# Uses GCS bucket
# Reads from Secret Manager
```

---

## 🔍 Post-Deployment

### Get Service URL
```bash
gcloud run services describe fin-sync --region=us-central1 --format="value(status.url)"
```

### View Logs
```bash
gcloud run services logs read fin-sync --region=us-central1
```

### Update Service
```bash
# Just redeploy
./deploy.sh
# Or
gcloud builds submit --config=cloudbuild.yaml
```

---

## ⚠️ Important Notes

1. **First Deploy**: Takes 5-10 minutes (builds Docker image)
2. **Cold Starts**: First request after idle may take 10-30s
3. **Auth**: Currently public (add `--no-allow-unauthenticated` for private)
4. **Costs**: Monitor usage in GCP Console
5. **Secrets**: Never commit `.env` file to git

---

## 🐛 Troubleshooting

### "Permission Denied"
```bash
# Grant yourself owner role
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/owner"
```

### "Service Won't Start"
```bash
# Check logs
gcloud run services logs read fin-sync --limit=100
```

### "Out of Memory"
```bash
# Increase memory
gcloud run services update fin-sync \
  --memory 4Gi \
  --region us-central1
```

---

## 📚 Full Documentation

See `DEPLOYMENT.md` for:
- Manual step-by-step deployment
- CI/CD setup
- Cost optimization
- Monitoring & alerts
- Security best practices

---

## ✨ Next Steps

1. ✅ Deploy app → `./deploy.sh`
2. 🔒 Set up authentication (optional)
3. 🌐 Add custom domain (optional)
4. 📊 Configure monitoring alerts
5. 🚀 Set up CI/CD with Cloud Build triggers

**Need Help?** Check logs: `gcloud run services logs read fin-sync --region=us-central1`

