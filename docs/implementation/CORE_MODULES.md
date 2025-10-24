# Core Modules Implementation

Core utilities, configuration, and infrastructure modules that form the foundation of FinSync.

---

## Module Overview

```
core/
├── __init__.py          # Package initialization
├── config.py            # Configuration management (Pydantic)
├── logger.py            # Structured logging (loguru)
├── secrets.py           # GCP Secret Manager integration
├── storage.py           # Storage backend abstraction
└── utils.py             # Common utilities
```

---

## 1. Configuration (`config.py`)

### Purpose
Centralized configuration using Pydantic Settings with environment variable support.

### Key Features
- ✅ **Type-safe** configuration with Pydantic
- ✅ **Environment-aware** (.env files per environment)
- ✅ **Validation** on startup
- ✅ **Secret Manager** integration in production
- ✅ **Automatic path** creation

### Usage

```python
from core.config import config

# Access configuration
project_id = config.gcp_project_id
model = config.vertex_model
elastic_endpoint = config.elastic_cloud_endpoint

# Environment-specific
if config.environment == "production":
    # Production logic
    pass
```

### Configuration Schema

```python
class AppConfig(BaseSettings):
    """Application configuration."""
    
    # Environment
    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    app_port: int = 8501
    
    # Upload limits
    max_total_mb: int = 100
    max_files: int = 25
    allowed_ext: tuple = ("pdf", "csv")
    
    # Paths
    data_dir: Path = Path("data")
    uploads_dir: Path | None = None
    logs_dir: Path = Path("data/output")
    log_file: Path | None = None
    
    # GCP / Vertex AI
    gcp_project_id: str | None = None
    gcp_location: str = "us-central1"
    vertex_model: str = "gemini-2.5-pro"
    vertex_model_genai: str = "gemini-2.5-pro"
    vertex_model_embed: str = "text-embedding-004"
    
    # Storage
    gcs_bucket: str | None = None
    
    # Elastic
    elastic_cloud_endpoint: str | None = None
    elastic_api_key: str | None = None
    elastic_index_transactions: str = "finsync-transactions"
    elastic_index_statements: str = "finsync-statements"
    elastic_vector_field: str = "desc_vector"
    elastic_vector_dim: int = 768
```

### Environment File Hierarchy

```
.env                      # Base configuration
.env.development          # Development overrides
.env.production           # Production overrides
.env.test                 # Test overrides
```

**Loading Priority** (highest to lowest):
1. Environment variables
2. `.env.{ENVIRONMENT}` file
3. `.env` file
4. Default values in code

### Validators

```python
@field_validator("log_level", mode="before")
@classmethod
def _normalize_log_level(cls, value: str) -> str:
    """Normalize and validate log level."""
    level = str(value).upper()
    allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    return level if level in allowed else "INFO"

@model_validator(mode="after")
def _derive_paths_and_ensure_dirs(self) -> "AppConfig":
    """Create directories on startup."""
    self.uploads_dir = self.uploads_dir or self.data_dir / "uploads"
    self.log_file = self.log_file or self.logs_dir / "app.log"
    
    # Ensure directories exist
    for path in [self.data_dir, self.uploads_dir, self.logs_dir]:
        path.mkdir(parents=True, exist_ok=True)
    
    return self
```

---

## 2. Logging (`logger.py`)

### Purpose
Structured logging with loguru, supporting both file and console output.

### Features
- ✅ **Structured logs** (JSON format)
- ✅ **Context fields** (extra data)
- ✅ **Rotation** (size-based)
- ✅ **Cloud Logging** compatible
- ✅ **Per-module loggers**

### Usage

```python
from core.logger import get_logger

log = get_logger("my_module")

# Simple logging
log.info("Processing file")
log.warning("Slow query detected")
log.error("Upload failed", exc_info=True)

# Structured logging
log.info(
    "Intent classified",
    extra={
        "intent": "aggregate",
        "confidence": 0.85,
        "processing_time_ms": 1234
    }
)
```

### Configuration

```python
def setup_logger(log_level: str = "INFO", log_file: Path | None = None):
    """
    Configure loguru logger.
    
    Args:
        log_level: Minimum log level
        log_file: Optional file path for logs
    """
    logger.remove()  # Remove default handler
    
    # Console handler (colorized)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # File handler (JSON for Cloud Logging)
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
            level=log_level,
            rotation="50 MB",  # Rotate at 50 MB
            retention="30 days",  # Keep logs for 30 days
            compression="zip"  # Compress rotated logs
        )
```

### Log Format

**Console** (human-readable):
```
2025-10-24 15:30:45 | INFO     | llm/intent_router:classify_intent | Intent classified
```

**File** (structured):
```
2025-10-24 15:30:45 | INFO     | llm/intent_router:classify_intent | Intent classified
```

### Best Practices

```python
# ✅ Good: Structured logging
log.info(
    "Query processed",
    extra={
        "query": query[:50],  # Truncate long strings
        "intent": intent,
        "latency_ms": elapsed
    }
)

# ✅ Good: Exception logging
try:
    result = risky_operation()
except Exception as e:
    log.exception("Operation failed")  # Includes stack trace
    
# ❌ Avoid: PII in logs
log.info(f"User {email} uploaded file")  # Email is PII

# ✅ Better: Redacted
log.info(f"User {hash(email)} uploaded file")
```

---

## 3. Secrets Management (`secrets.py`)

### Purpose
Load secrets from GCP Secret Manager in production, .env files in development.

### Usage

```python
# Automatically loaded in core/config.py
if os.getenv("ENVIRONMENT") == "production" and os.getenv("USE_SECRET_MANAGER") == "true":
    from core.secrets import load_secrets_into_env
    load_secrets_into_env()
```

### Implementation

```python
def load_secrets_into_env():
    """
    Load secrets from GCP Secret Manager into environment variables.
    
    Secrets loaded:
    - ELASTIC_CLOUD_ENDPOINT
    - ELASTIC_API_KEY
    """
    from google.cloud import secretmanager
    
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.getenv("GCP_PROJECT_ID")
    
    secrets_to_load = [
        "ELASTIC_CLOUD_ENDPOINT",
        "ELASTIC_API_KEY"
    ]
    
    for secret_name in secrets_to_load:
        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            value = response.payload.data.decode("UTF-8")
            os.environ[secret_name] = value
            log.info(f"Loaded secret: {secret_name}")
        except Exception as e:
            log.error(f"Failed to load secret {secret_name}: {e}")
```

### Security Best Practices

```python
# ✅ Good: Use Secret Manager in production
if config.environment == "production":
    api_key = load_from_secret_manager("ELASTIC_API_KEY")

# ✅ Good: Never log secrets
log.info("Loaded API key")  # Don't log the actual key

# ✅ Good: Validate secrets loaded
if not config.elastic_api_key:
    raise RuntimeError("ELASTIC_API_KEY not set")

# ❌ Avoid: Hardcoded secrets
API_KEY = "abc123..."  # Never do this
```

---

## 4. Storage Backend (`storage.py`)

See [Storage Backend Documentation](./STORAGE_BACKEND.md) for full details.

### Quick Reference

```python
from core.storage import get_storage_backend

# Automatic backend selection
storage = get_storage_backend()

# Save file
path = storage.save_file(file_obj, "statement.pdf")

# Read file
content = storage.read_file("statement.pdf")

# List files
files = storage.list_files(prefix="session-123/")

# Delete file
storage.delete_file("old_statement.pdf")
```

---

## 5. Common Utilities (`utils.py`)

### Purpose
Shared utility functions used across the application.

### Functions

#### File Operations

```python
def safe_write(path: Path, content: bytes | str) -> None:
    """
    Safely write to file with atomic operation.
    
    Creates parent directories if needed.
    Uses temp file + rename for atomicity.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "wb" if isinstance(content, bytes) else "w") as f:
        f.write(content)
    
    # Atomic rename
    temp_path.replace(path)
```

#### Date/Time Utilities

```python
def parse_date_flexible(date_str: str) -> datetime:
    """
    Parse date from various formats.
    
    Supports:
    - "2025-01-15"
    - "Jan 15, 2025"
    - "15/01/2025"
    - "last month"
    - "Q1 2025"
    """
    # Try ISO format first
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass
    
    # Try relative dates
    if "last month" in date_str.lower():
        return datetime.now() - timedelta(days=30)
    
    # Try dateutil parser
    from dateutil import parser
    return parser.parse(date_str)
```

#### Hash Utilities

```python
def compute_file_hash(file_path: Path | str) -> str:
    """
    Compute SHA-256 hash of file.
    
    Args:
        file_path: Path to file
        
    Returns:
        Hex digest of SHA-256 hash
    """
    import hashlib
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    
    return sha256.hexdigest()
```

#### String Utilities

```python
def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename."""
    import re
    # Remove invalid chars
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    return truncate(filename, max_length=255, suffix="")
```

---

## Testing

### Unit Tests

```python
# tests/test_config.py
def test_config_loads():
    from core.config import config
    assert config.environment in ["development", "production", "test"]
    assert config.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]

# tests/test_logger.py
def test_logger_creation():
    from core.logger import get_logger
    log = get_logger("test")
    assert log is not None
    log.info("Test message")

# tests/test_utils.py
def test_safe_write(tmp_path):
    from core.utils import safe_write
    file_path = tmp_path / "test.txt"
    safe_write(file_path, "test content")
    assert file_path.read_text() == "test content"
```

---

## Best Practices

### Configuration

✅ **Use config singleton**: `from core.config import config`  
✅ **Validate on startup**: Pydantic validators  
✅ **Environment-specific files**: .env.development, .env.production  
❌ **Don't import os.getenv() directly**: Use config object

### Logging

✅ **Get module-specific logger**: `log = get_logger(__name__)`  
✅ **Use structured logging**: `log.info("...", extra={...})`  
✅ **Log at appropriate level**: DEBUG < INFO < WARNING < ERROR  
❌ **Don't log secrets or PII**: Redact sensitive data

### Secrets

✅ **Use Secret Manager in production**: Auto-loads in Cloud Run  
✅ **Use .env in development**: Gitignored  
✅ **Validate required secrets**: Fail fast if missing  
❌ **Never commit secrets**: Use .gitignore

---

**Related**: [Storage Backend](./STORAGE_BACKEND.md) | [Configuration Guide](../deployment/CONFIGURATION.md)

