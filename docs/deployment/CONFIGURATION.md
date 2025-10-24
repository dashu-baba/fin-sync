# Configuration Guide

Complete reference for all configuration options in FinSync.

---

## Environment Variables

### Required (All Environments)

```bash
# GCP Project
GCP_PROJECT_ID=your-gcp-project-id

# Elastic Cloud
ELASTIC_CLOUD_ENDPOINT=https://your-deployment.es.cloud.es.io:443
ELASTIC_API_KEY=your-elastic-api-key
```

### Optional (Has Defaults)

```bash
# Environment
ENVIRONMENT=development  # development | staging | production | test
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL
APP_PORT=8501           # Port for Streamlit

# GCP Settings
GCP_LOCATION=us-central1  # GCP region for Vertex AI
GCS_BUCKET=your-project-finsync-uploads  # GCS bucket (production only)

# Vertex AI Models
VERTEX_MODEL=gemini-2.5-pro          # Document parsing model
VERTEX_MODEL_GENAI=gemini-2.5-pro    # Chat & classification model
VERTEX_MODEL_EMBED=text-embedding-004       # Embedding model (768-dim)

# Elastic Cloud
ELASTIC_INDEX_NAME=finsync-transactions          # Legacy index name
ELASTIC_IDX_TRANSACTIONS=finsync-transactions    # Transaction data stream
ELASTIC_IDX_STATEMENTS=finsync-statements        # Statement vector index
ELASTIC_IDX_AGG_MONTHLY=finsync-aggregates-monthly    # Monthly rollup index
ELASTIC_TXN_MONTHLY_TRANSFORM_ID=finsync_txn_monthly  # Transform ID
ELASTIC_ALIAS_TXN_VIEW=finsync-transactions-view      # Transaction alias
ELASTIC_VECTOR_FIELD=desc_vector            # Vector field name
ELASTIC_VECTOR_DIM=768                      # Embedding dimensions

# Production Only
USE_SECRET_MANAGER=false  # Set to true in Cloud Run
```

---

## Environment Files

### Development (`.env.development`)

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
GCP_PROJECT_ID=your-dev-project
ELASTIC_CLOUD_ENDPOINT=https://dev-cluster.es.cloud.es.io:443
ELASTIC_API_KEY=dev-api-key
# GCS_BUCKET not set - uses local storage
```

### Production (`.env.production`)

```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
USE_SECRET_MANAGER=true  # Load secrets from GCP
GCP_PROJECT_ID=your-prod-project
GCS_BUCKET=your-prod-project-finsync-uploads
# ELASTIC_* loaded from Secret Manager
```

### Test (`.env.test`)

```bash
ENVIRONMENT=test
LOG_LEVEL=WARNING
GCP_PROJECT_ID=your-test-project
ELASTIC_IDX_TRANSACTIONS=finsync-transactions-test
ELASTIC_IDX_STATEMENTS=finsync-statements-test
```

---

## Secret Manager Setup (Production)

### 1. Create Secrets

```bash
# Elastic credentials
echo "https://prod.es.cloud.es.io:443" | \
  gcloud secrets create ELASTIC_CLOUD_ENDPOINT --data-file=-

echo "your-elastic-api-key" | \
  gcloud secrets create ELASTIC_API_KEY --data-file=-
```

### 2. Grant Access to Cloud Run

```bash
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")

# Grant access to ELASTIC_API_KEY
gcloud secrets add-iam-policy-binding ELASTIC_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant access to ELASTIC_CLOUD_ENDPOINT
gcloud secrets add-iam-policy-binding ELASTIC_CLOUD_ENDPOINT \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Configure Cloud Run

```bash
gcloud run deploy fin-sync \
  --set-env-vars USE_SECRET_MANAGER=true \
  --set-secrets ELASTIC_API_KEY=ELASTIC_API_KEY:latest,ELASTIC_CLOUD_ENDPOINT=ELASTIC_CLOUD_ENDPOINT:latest
```

---

## Model Configuration

### Choosing Models

| Use Case | Recommended Model | Cost | Quality |
|----------|------------------|------|---------|
| **Document Parsing** | `gemini-2.5-pro` | $$$ | Best |
| **Intent Classification** | `gemini-2.5-pro` | $$$ | Best |
| **Chat** | `gemini-2.5-pro` | $$$ | Best |
| **Fast Classification** | `gemini-2.0-flash-exp` | $ | Good |
| **Embeddings** | `text-embedding-004` | $ | Best |

### Cost vs Quality Trade-off

```bash
# Default (Good Balance)
VERTEX_MODEL=gemini-2.0-flash-exp
VERTEX_MODEL_GENAI=gemini-2.0-flash-exp

# High Quality Option
VERTEX_MODEL=gemini-2.5-pro
VERTEX_MODEL_GENAI=gemini-2.5-pro
```

---

## Storage Configuration

### Local Storage (Development)

```bash
ENVIRONMENT=development
# GCS_BUCKET not set
# Files saved to: data/uploads/
```

### GCS Storage (Production)

```bash
ENVIRONMENT=production
GCS_BUCKET=your-project-finsync-uploads
# Files saved to: gs://your-project-finsync-uploads/
```

---

## Elastic Configuration

### Index Names

```bash
# Transaction data stream (for aggregations)
ELASTIC_IDX_TRANSACTIONS=finsync-transactions

# Statement vector index (for semantic search)
ELASTIC_IDX_STATEMENTS=finsync-statements
```

### Vector Settings

```bash
# Embedding field name in statements index
ELASTIC_VECTOR_FIELD=desc_vector

# Embedding dimensions (must match model)
# text-embedding-004: 768
# textembedding-gecko@003: 768
ELASTIC_VECTOR_DIM=768
```

---

## Validation

### Check Configuration

```python
from core.config import config

# Print all config
print(f"Environment: {config.environment}")
print(f"GCP Project: {config.gcp_project_id}")
print(f"Elastic Endpoint: {config.elastic_cloud_endpoint}")
print(f"GCS Bucket: {config.gcs_bucket or 'Local storage'}")
```

### Verify Secrets (Production)

```bash
# Test Secret Manager access
gcloud secrets versions access latest --secret=ELASTIC_API_KEY

# Verify Cloud Run has access
gcloud run services describe fin-sync --region=us-central1 | grep secrets
```

---

## Troubleshooting

### Issue: Config not loading

**Check**:
```bash
# Verify .env file exists
ls -la .env*

# Check environment variable
echo $ENVIRONMENT
```

### Issue: Secrets not loading in Cloud Run

**Check**:
```bash
# Verify secrets exist
gcloud secrets list

# Check IAM permissions
gcloud secrets get-iam-policy ELASTIC_API_KEY

# View Cloud Run logs
gcloud run services logs read fin-sync --limit=50
```

### Issue: Wrong model used

**Check**:
```python
from core.config import config
print(f"Model: {config.vertex_model}")
print(f"GenAI Model: {config.vertex_model_genai}")
```

---

**Related**: [Quickstart](./QUICKSTART.md) | [GCP Deployment](./GCP_DEPLOYMENT.md)

