# Storage Backend Implementation

## Overview

FinSync uses an intelligent storage abstraction layer that **automatically switches between local filesystem and Google Cloud Storage (GCS)** based on the deployment environment. This allows seamless development locally while leveraging cloud storage in production.

## Architecture

### Storage Abstraction Layer

```
┌─────────────────────────────────────────┐
│         Application Code                 │
│   (Upload Service, Parse Service)        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Storage Backend Factory             │
│    get_storage_backend()                 │
└──────────────┬──────────────────────────┘
               │
               ├──────────────┬─────────────┐
               ▼              ▼             ▼
    ┌─────────────────┐  ┌──────────┐  ┌──────────┐
    │ LocalStorage    │  │ GCSStorage│  │ Future   │
    │ (Development)   │  │(Production)│  │ Backends │
    └─────────────────┘  └──────────┘  └──────────┘
```

### Storage Backend Interface

All storage backends implement the `StorageBackend` abstract class:

```python
class StorageBackend:
    def save_file(file_obj: BinaryIO, destination_path: str) -> str
    def read_file(file_path: str) -> bytes
    def delete_file(file_path: str) -> None
    def list_files(prefix: str = "") -> list[str]
```

## Implementation Details

### 1. Local Storage (`LocalStorage`)

**Used for**: Development, staging, testing

**Characteristics**:
- Stores files in `data/uploads/` directory
- Fast read/write operations
- No network latency
- Easy debugging and inspection
- Automatic directory creation

**Configuration**:
```bash
# .env or .env.development
ENVIRONMENT=development
# GCS_BUCKET not set or empty
```

**Example usage**:
```python
storage = LocalStorage(base_dir=Path("data/uploads"))
storage.save_file(file_obj, "statement.pdf")
# Saves to: data/uploads/statement.pdf
```

### 2. Google Cloud Storage (`GCSStorage`)

**Used for**: Production

**Characteristics**:
- Stores files in GCS bucket
- Scalable and durable
- Supports large files (up to 5TB)
- Automatic retry on failure
- Integrated with GCP ecosystem

**Configuration**:
```bash
# .env.production
ENVIRONMENT=production
GCS_BUCKET=your-project-finsync-uploads
```

**Example usage**:
```python
storage = GCSStorage(bucket_name="my-finsync-uploads")
storage.save_file(file_obj, "statement.pdf")
# Saves to: gs://my-finsync-uploads/statement.pdf
```

### 3. Auto-Detection Factory

The `get_storage_backend()` function automatically selects the appropriate backend:

```python
def get_storage_backend() -> StorageBackend:
    """Factory function to get appropriate storage backend."""
    from core.config import config
    
    if config.gcs_bucket and config.environment == "production":
        logger.info("Using GCS storage backend")
        return GCSStorage(config.gcs_bucket)
    else:
        logger.info("Using local storage backend")
        return LocalStorage(config.uploads_dir)
```

**Decision Logic**:
- If `ENVIRONMENT=production` **AND** `GCS_BUCKET` is set → **GCS**
- Otherwise → **Local**

## Integration with Upload Service

### File Upload Process

```python
# In ui/services/upload_service.py

def process_upload(
    file: UploadedFile,
    upload_dir: Path,
    password: Optional[str] = None,
    use_storage_backend: bool = None
) -> Optional[Dict]:
    """Process uploaded file with automatic storage backend detection."""
    
    # Auto-detect storage backend
    if use_storage_backend is None:
        use_storage_backend = (
            config.environment == "production" and 
            config.gcs_bucket is not None
        )
    
    if use_storage_backend:
        # Use storage backend (GCS or local via abstraction)
        storage = get_storage_backend()
        file_obj = BytesIO(file.getvalue())
        file_path = storage.save_file(file_obj, file.name)
    else:
        # Direct local filesystem (dev mode)
        target_path = upload_dir / file.name
        safe_write(target_path, file.getvalue())
```

### Duplicate Detection

Duplicate detection works with **both** storage backends:

```python
def check_duplicate_by_hash(
    file_content: bytes,
    upload_dir: Path,
    use_storage_backend: bool = False
) -> Tuple[bool, Optional[str]]:
    """Check for duplicate files in local or GCS storage."""
    
    if use_storage_backend:
        # Use storage backend (works for both local and GCS)
        storage = get_storage_backend()
        files = storage.list_files()
        
        for file_path in files:
            existing_content = storage.read_file(file_path)
            if sha256(existing_content) == sha256(file_content):
                return True, Path(file_path).name
    else:
        # Direct filesystem check
        for existing_file in upload_dir.glob("*.pdf"):
            with open(existing_file, "rb") as f:
                if sha256(f.read()) == sha256(file_content):
                    return True, existing_file.name
    
    return False, None
```

## Configuration

### Environment Variables

```bash
# Required for all environments
GCP_PROJECT_ID=your-gcp-project-id

# Local Development (.env.development)
ENVIRONMENT=development
# GCS_BUCKET not set - uses local storage

# Production (.env.production)
ENVIRONMENT=production
GCS_BUCKET=your-project-finsync-uploads  # REQUIRED for GCS
```

### GCS Bucket Setup

#### 1. Create GCS Bucket

```bash
# Create bucket
gsutil mb -p YOUR_PROJECT_ID \
  -c STANDARD \
  -l us-central1 \
  gs://your-project-finsync-uploads

# Set lifecycle policy (optional - auto-delete old files)
gsutil lifecycle set lifecycle.json gs://your-project-finsync-uploads
```

#### 2. Set Permissions

```bash
# Grant service account access
gsutil iam ch serviceAccount:YOUR-SERVICE-ACCOUNT@PROJECT.iam.gserviceaccount.com:roles/storage.objectAdmin \
  gs://your-project-finsync-uploads
```

#### 3. Configure CORS (if needed)

```bash
# cors.json
[
  {
    "origin": ["https://your-app-url.run.app"],
    "method": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]

gsutil cors set cors.json gs://your-project-finsync-uploads
```

## File Path Handling

### Path Formats

| Storage Type | Format | Example |
|--------------|--------|---------|
| Local | Absolute path | `/app/data/uploads/statement.pdf` |
| GCS | GS URI | `gs://bucket-name/statement.pdf` |

### Normalized Metadata

The upload service returns consistent metadata regardless of storage:

```python
{
    "name": "statement.pdf",
    "ext": "pdf",
    "size_bytes": 1024000,
    "size_human": "1.0 MB",
    "path": "gs://bucket/statement.pdf" or "/app/data/uploads/statement.pdf",
    "storage_type": "gcs" or "local"
}
```

## Benefits

### Development Experience
- ✅ **Fast Local Testing** - No network calls during development
- ✅ **Easy Debugging** - Files visible in filesystem
- ✅ **Offline Development** - Works without internet
- ✅ **No GCP Costs** - Free local storage

### Production Reliability
- ✅ **Scalable Storage** - GCS handles any file volume
- ✅ **High Durability** - 99.999999999% durability
- ✅ **Global Access** - Files available from anywhere
- ✅ **Automatic Backup** - Built-in redundancy

### Code Quality
- ✅ **Single Codebase** - Same code for dev and prod
- ✅ **Testable** - Easy to mock storage backends
- ✅ **Extensible** - Easy to add new backends (S3, Azure, etc.)

## Usage Examples

### Basic Upload

```python
from core.storage import get_storage_backend

# Get appropriate backend (auto-detects)
storage = get_storage_backend()

# Save file
with open("local_file.pdf", "rb") as f:
    path = storage.save_file(f, "statement.pdf")
    print(f"Saved to: {path}")
```

### List Files

```python
storage = get_storage_backend()
files = storage.list_files()

print(f"Found {len(files)} files:")
for file_path in files:
    print(f"  - {file_path}")
```

### Read File

```python
storage = get_storage_backend()
content = storage.read_file("statement.pdf")
print(f"Read {len(content)} bytes")
```

### Delete File

```python
storage = get_storage_backend()
storage.delete_file("old_statement.pdf")
print("File deleted")
```

## Error Handling

### Graceful Fallback

The upload service includes fallback logic:

```python
if use_storage_backend:
    try:
        storage = get_storage_backend()
        # ... use storage backend ...
    except Exception as e:
        log.error(f"Storage backend failed: {e}")
        # Fall through to local filesystem
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Bucket not found` | GCS_BUCKET doesn't exist | Create bucket or fix name |
| `Permission denied` | Missing IAM permissions | Grant storage.objectAdmin |
| `File not found` | File doesn't exist | Check file path |
| `Connection timeout` | Network issues | Check connectivity |

## Testing

### Local Testing

```bash
# Set environment to development
export ENVIRONMENT=development

# Run application
python main.py

# Files saved to: data/uploads/
ls -lh data/uploads/
```

### Production Testing

```bash
# Set environment to production
export ENVIRONMENT=production
export GCS_BUCKET=your-project-finsync-uploads

# Run application
python main.py

# Check GCS bucket
gsutil ls gs://your-project-finsync-uploads/
```

### Unit Tests

```python
def test_local_storage():
    storage = LocalStorage(Path("test_uploads"))
    
    # Test save
    content = b"test content"
    path = storage.save_file(BytesIO(content), "test.pdf")
    assert Path(path).exists()
    
    # Test read
    read_content = storage.read_file("test.pdf")
    assert read_content == content
    
    # Test delete
    storage.delete_file("test.pdf")
    assert not Path(path).exists()
```

## Performance Considerations

### Local Storage
- **Save**: < 10ms for typical PDF (2-5MB)
- **Read**: < 10ms
- **List**: < 5ms (small directories)

### GCS Storage
- **Save**: 100-500ms (network latency)
- **Read**: 100-300ms
- **List**: 50-200ms

**Recommendation**: Use local storage for development to maximize speed.

## Monitoring

### Logs

Storage operations are automatically logged:

```
2025-10-24 15:20:01 | INFO | Using local storage backend
2025-10-24 15:20:02 | INFO | Saved file to local storage: /app/data/uploads/statement.pdf
2025-10-24 15:20:03 | INFO | Upload mode: local filesystem
```

### Metrics to Track

1. **Storage backend type** - Local vs GCS usage
2. **Upload duration** - Time to save files
3. **Storage size** - Total uploaded bytes
4. **Error rate** - Failed upload attempts

## Migration Guide

### From Local to GCS

1. **Create GCS bucket**:
   ```bash
   gsutil mb gs://your-project-finsync-uploads
   ```

2. **Update environment**:
   ```bash
   export ENVIRONMENT=production
   export GCS_BUCKET=your-project-finsync-uploads
   ```

3. **Optional: Migrate existing files**:
   ```bash
   gsutil -m cp -r data/uploads/* gs://your-project-finsync-uploads/
   ```

4. **Verify**:
   ```bash
   gsutil ls gs://your-project-finsync-uploads/
   ```

### From GCS to Local

1. **Download files** (optional):
   ```bash
   gsutil -m cp -r gs://your-project-finsync-uploads/* data/uploads/
   ```

2. **Update environment**:
   ```bash
   export ENVIRONMENT=development
   unset GCS_BUCKET
   ```

## Security Considerations

### Local Storage
- ✅ Files only accessible to application user
- ✅ No network exposure
- ⚠️ Not backed up by default
- ⚠️ Limited to single machine

### GCS Storage
- ✅ Encrypted at rest (Google-managed keys)
- ✅ Encrypted in transit (TLS)
- ✅ IAM-based access control
- ✅ Audit logging available
- ⚠️ Requires proper IAM configuration

## Troubleshooting

### Issue: Files saved locally in production

**Cause**: `GCS_BUCKET` not set or `ENVIRONMENT` not set to "production"

**Solution**:
```bash
export ENVIRONMENT=production
export GCS_BUCKET=your-project-finsync-uploads
```

### Issue: Permission denied in GCS

**Cause**: Service account missing storage permissions

**Solution**:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA@PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### Issue: Duplicate detection not working

**Cause**: `use_storage_backend` parameter not passed correctly

**Solution**: Verify the parameter is passed in upload calls:
```python
is_duplicate, _ = UploadService.check_duplicate_by_hash(
    content, upload_dir, use_storage_backend=True  # ← Important!
)
```

## Future Enhancements

Potential improvements:

1. **Additional Backends**
   - AWS S3 support
   - Azure Blob Storage
   - MinIO for self-hosted S3-compatible storage

2. **Caching Layer**
   - Redis cache for file metadata
   - Local cache for frequently accessed files

3. **Advanced Features**
   - Multipart uploads for large files
   - Resume interrupted uploads
   - File compression before storage
   - CDN integration for faster downloads

4. **Management UI**
   - Web interface to view/manage uploads
   - Bulk delete operations
   - Storage analytics dashboard

## Conclusion

The storage backend abstraction provides a clean, flexible way to handle file uploads in FinSync. It allows developers to work efficiently locally while seamlessly scaling to cloud storage in production, all with the same codebase.

**Key Takeaway**: The system automatically uses the right storage for the environment, requiring minimal configuration and zero code changes.

