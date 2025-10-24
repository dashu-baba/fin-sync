# Deployment Integration TODO

## ✅ Completed

1. **Infrastructure Files**
   - ✅ `Dockerfile` - Production-ready container
   - ✅ `cloudbuild.yaml` - Automated build & deploy
   - ✅ `.dockerignore` - Optimized builds
   - ✅ `.env.example` - Environment template
   - ✅ `deploy.sh` - One-click deployment script

2. **Core Updates**
   - ✅ `core/storage.py` - GCS/Local storage abstraction
   - ✅ `core/secrets.py` - Secret Manager integration
   - ✅ `core/config.py` - Secret Manager support
   - ✅ `requirements.txt` - Added Secret Manager dependency

3. **Documentation**
   - ✅ `DEPLOYMENT.md` - Complete guide
   - ✅ `QUICKSTART_DEPLOY.md` - Quick reference

## 🔧 Integration Needed (Optional)

### 1. Update Upload Service to Use GCS
**File**: `ui/services/upload_service.py`

Currently saves to local `data/uploads/`. Update to:
```python
from core.storage import get_storage_backend

storage = get_storage_backend()
path = storage.save_file(uploaded_file, f"uploads/{filename}")
```

### 2. Update PDF Reader for GCS
**File**: `ingestion/pdf_reader.py`

Add support for reading from GCS paths:
```python
from core.storage import get_storage_backend

def read_pdf(file_path: str) -> bytes:
    if file_path.startswith("gs://"):
        storage = get_storage_backend()
        return storage.read_file(file_path)
    # ... existing local file logic
```

### 3. Update Parse Service
**File**: `ui/services/parse_service.py`

Use storage backend for file operations:
```python
storage = get_storage_backend()
files = storage.list_files(prefix="uploads/")
```

### 4. Use Cloud Logging
**File**: `core/logger.py`

Add Google Cloud Logging handler for production:
```python
if config.environment == "production":
    import google.cloud.logging
    client = google.cloud.logging.Client()
    client.setup_logging()
```

## 🚀 Current State

### Works Out of Box:
- ✅ Deploy to Cloud Run
- ✅ Vertex AI integration (uses default credentials)
- ✅ Elastic Cloud connection
- ✅ Secret Manager for credentials
- ✅ Streamlit UI
- ✅ Local file storage (works but not ideal for production)

### Production-Ready With GCS:
After updating the 3 files above, the app will:
- Store PDFs in GCS (persistent, scalable)
- Handle multi-instance deployments
- Scale horizontally without file conflicts

## 📝 Quick Fix Priority

**Option A: Deploy Now (Works)**
- Use current code
- Files stored locally (ephemeral, lost on restart)
- Good for: Testing, demos, low-traffic

**Option B: Add GCS (Recommended)**
- Takes ~30 min to integrate
- Production-ready
- Good for: Real users, multi-instance scaling

## 🔍 Files to Update for GCS

1. **`ui/services/upload_service.py`** - Line ~20-30 (file save)
2. **`ingestion/pdf_reader.py`** - Line ~15-25 (file read)
3. **`ui/services/parse_service.py`** - Line ~40-50 (list files)

Search for: `data/uploads` or `uploads_dir` to find exact locations.

## 💡 Testing Plan

### Local Testing
```bash
# Test with local storage
ENVIRONMENT=development python -m streamlit run ui/app.py
```

### Production Testing
```bash
# Deploy to Cloud Run
./deploy.sh

# Test upload flow
# Check GCS bucket for files
gsutil ls gs://PROJECT_ID-finsync-uploads/
```

## 📊 Migration Path

If you want to migrate existing local files to GCS:
```bash
# Sync local uploads to GCS
gsutil -m rsync -r data/uploads/ gs://PROJECT_ID-finsync-uploads/uploads/
```

## ⚡ Deploy Now?

You can deploy **right now** with:
```bash
./deploy.sh
```

The app will work, but use local storage. Add GCS integration later when needed.

