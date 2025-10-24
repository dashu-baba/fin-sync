# Local Development Setup

Complete guide to setting up FinSync for local development.

---

## Prerequisites

- **Python 3.11+** (required)
- **Google Cloud SDK** (for Vertex AI)
- **Git** (for cloning repository)
- **Elastic Cloud account** (for search)

---

## Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/dashu-baba/fin-sync.git
cd fin-sync

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Authenticate with GCP
gcloud auth application-default login

# 5. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 6. Run application
python main.py
```

Access at: `http://localhost:8501`

---

## Detailed Setup

### 1. Python Environment

```bash
# Check Python version
python --version  # Should be 3.11+

# Create virtual environment
python3.11 -m venv venv

# Activate
source venv/bin/activate  # Unix/Mac
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip
```

### 2. Install Dependencies

```bash
# Install all packages
pip install -r requirements.txt

# Verify installation
pip list | grep -E "streamlit|google-cloud|elastic"
```

**Key Packages**:
- `streamlit==1.39.0` - UI framework
- `google-cloud-aiplatform>=1.68.0` - Vertex AI
- `elasticsearch>=8.15.0` - Elastic client
- `pydantic>=2.9.2` - Data validation
- `loguru>=0.7.2` - Logging

### 3. GCP Setup

```bash
# Install gcloud CLI (if not installed)
# See: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud auth application-default login

# Set project
export GCP_PROJECT_ID=your-project-id
gcloud config set project $GCP_PROJECT_ID

# Enable APIs
gcloud services enable \
  aiplatform.googleapis.com \
  storage.googleapis.com
```

### 4. Elastic Cloud Setup

1. **Create account**: https://cloud.elastic.co/registration
2. **Create deployment** (Free tier available)
3. **Get credentials**:
   - Endpoint: `https://your-id.es.cloud.es.io:443`
   - API Key: Generate in Kibana → Stack Management → API Keys

### 5. Environment Configuration

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env  # or vim, code, etc.
```

**Minimum required** (`.env`):
```bash
# GCP
GCP_PROJECT_ID=your-gcp-project-id

# Elastic
ELASTIC_CLOUD_ENDPOINT=https://your-deployment.es.cloud.es.io:443
ELASTIC_API_KEY=your-elastic-api-key
```

**Optional** (has defaults):
```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
APP_PORT=8501
VERTEX_MODEL=gemini-2.5-pro
```

---

## Running the Application

### Method 1: Using main.py (Recommended)

```bash
python main.py
```

### Method 2: Direct Streamlit

```bash
streamlit run ui/app.py --server.port 8501
```

### Method 3: Custom Port

```bash
export PORT=8080
python main.py
```

---

## Verify Setup

### 1. Check Configuration

```bash
python -c "from core.config import config; print(f'Project: {config.gcp_project_id}, Environment: {config.environment}')"
```

### 2. Test Vertex AI

```bash
python -c "from google.cloud import aiplatform; aiplatform.init(project='YOUR_PROJECT'); print('Vertex AI OK')"
```

### 3. Test Elastic

```bash
python -c "from elastic.client import es; print('Elastic OK') if es().ping() else print('Elastic FAIL')"
```

### 4. Test Complete Stack

```bash
# Run test script
python scripts/test_intent_router.py
```

---

## Development Workflow

### 1. Code Changes

```bash
# Make changes to code
# Streamlit auto-reloads on file save
```

### 2. Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test
python scripts/test_intent_router.py
```

### 3. Check Logs

```bash
# View application logs
tail -f data/output/app.log

# Or in Streamlit terminal
```

### 4. Debug

```python
# Add debug logging
from core.logger import get_logger
log = get_logger(__name__)

log.debug("Debug info", extra={"data": some_data})
```

---

## IDE Setup

### VS Code

**Recommended extensions**:
- Python (Microsoft)
- Pylance (Microsoft)
- Ruff (Astral Software)

**Settings** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

### PyCharm

1. **Set interpreter**: Settings → Project → Python Interpreter → Add venv
2. **Enable type checking**: Settings → Editor → Inspections → Python
3. **Configure run**: Run → Edit Configurations → Add Python → Script: `main.py`

---

## Common Issues

### Issue: ModuleNotFoundError

```bash
# Solution: Ensure venv is activated
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Vertex AI authentication error

```bash
# Solution: Re-authenticate
gcloud auth application-default login
```

### Issue: Elastic connection timeout

```bash
# Solution: Check endpoint and API key
curl -H "Authorization: ApiKey YOUR_API_KEY" \
  https://your-deployment.es.cloud.es.io:443
```

### Issue: Port already in use

```bash
# Solution: Use different port
export PORT=8502
python main.py
```

---

## Development Tips

### Hot Reload

Streamlit auto-reloads on file changes. Just save and refresh browser.

### Debug Mode

```bash
LOG_LEVEL=DEBUG python main.py
```

### Profile Performance

```python
import time
start = time.time()
result = expensive_function()
print(f"Took {time.time() - start:.2f}s")
```

### Interactive Shell

```bash
# Python REPL with imports
python
>>> from core.config import config
>>> from elastic.client import es
>>> es().ping()
True
```

---

**Related**: [API Reference](./API_REFERENCE.md) | [Testing](./TESTING.md)

