# Technology Stack Deep Dive

This document provides detailed rationale for each technology choice in FinSync.

---

## Technology Matrix

| Layer | Technology | Version | Purpose | Alternatives Considered |
|-------|-----------|---------|---------|------------------------|
| **Frontend** | Streamlit | 1.39+ | Interactive UI | React, Vue, Gradio |
| **Backend** | Python | 3.11+ | Application logic | Node.js, Go |
| **LLM** | Gemini 2.5 Pro | Latest | NLU, parsing, chat | GPT-4, Claude |
| **Embeddings** | text-embedding-004 | - | Semantic vectors | OpenAI, Cohere |
| **Search** | Elastic Cloud | 8.15+ | Hybrid search | Pinecone, Weaviate |
| **Storage** | GCS / Local | - | File storage | S3, Azure Blob |
| **Deployment** | Cloud Run | - | Serverless hosting | App Engine, GKE |
| **CI/CD** | Cloud Build | - | Automated deploy | GitHub Actions |
| **Secrets** | Secret Manager | - | Credential storage | Vault, AWS Secrets |

---

## Frontend: Streamlit

### Why Streamlit?

**Pros**:
- ✅ **Rapid Development**: Build UI with pure Python
- ✅ **Session State**: Built-in state management
- ✅ **Components**: Rich component library (charts, forms, etc.)
- ✅ **Prototyping**: Perfect for data/AI applications
- ✅ **No JavaScript**: Python developers can work full-stack
- ✅ **Free Hosting**: Streamlit Community Cloud available

**Cons**:
- ❌ **Limited Customization**: CSS/JS limited
- ❌ **Performance**: Not ideal for high-traffic apps
- ❌ **Mobile**: Desktop-first, mobile second
- ❌ **SEO**: Not SEO-friendly

### When to Consider Alternatives

- **High traffic** (>10K DAU) → React + FastAPI
- **Complex UI** (custom layouts) → React + Tailwind
- **Mobile-first** → React Native or Flutter
- **Public website** (SEO needed) → Next.js

### Streamlit Best Practices in FinSync

```python
# ✅ Good: Cache expensive operations
@st.cache_data(ttl=600)
def load_analytics_data():
    return fetch_from_elastic()

# ✅ Good: Use session state for multi-page state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ✅ Good: Componentize reusable UI
def render_transaction_card(txn):
    with st.container():
        st.write(f"**{txn['date']}**: ${txn['amount']}")

# ❌ Avoid: Heavy computation in main render
# Move to background or cache
```

---

## Backend: Python 3.11+

### Why Python?

**Pros**:
- ✅ **AI/ML Ecosystem**: Best-in-class libraries (Pydantic, transformers)
- ✅ **Developer Productivity**: Fast iteration
- ✅ **Type Hints**: Modern Python has good type safety
- ✅ **Async Support**: asyncio for I/O-bound tasks
- ✅ **Community**: Largest AI/data science community

**Cons**:
- ❌ **Performance**: Slower than Go/Rust for CPU-bound tasks
- ❌ **Concurrency**: GIL limits multi-threading
- ❌ **Deployment Size**: Larger container images

### Why Python 3.11+?

- **Performance**: 10-60% faster than 3.10
- **Better error messages**: Easier debugging
- **Type system improvements**: Better with Pydantic
- **ExceptionGroups**: Better async error handling

### Python Best Practices in FinSync

```python
# ✅ Type hints everywhere
def parse_statement(text: str) -> ParsedStatement:
    ...

# ✅ Pydantic for validation
class Config(BaseSettings):
    gcp_project_id: str
    elastic_endpoint: str

# ✅ Structured logging
log.info("Processing file", extra={"file_size": size, "session": session_id})

# ✅ Context managers for resources
with open(file_path, "rb") as f:
    content = f.read()
```

---

## LLM: Google Vertex AI (Gemini 2.5 Pro)

### Why Gemini?

**Pros**:
- ✅ **GCP Integration**: Native Cloud Run integration
- ✅ **Multimodal**: Text, images, PDFs (future)
- ✅ **JSON Mode**: Reliable structured output
- ✅ **Cost**: Competitive pricing vs GPT-4
- ✅ **Latency**: Fast response times
- ✅ **Context Window**: 1M+ tokens (2.5 Pro)

**Cons**:
- ❌ **Vendor Lock-in**: GCP-specific
- ❌ **Less Adoption**: Smaller community vs OpenAI
- ❌ **Prompt Compatibility**: Different from GPT-4

### Model Selection

| Model | Use Case | Cost | Latency |
|-------|----------|------|---------|
| `gemini-2.5-pro` | Complex parsing, chat | $$ | Medium |
| `gemini-2.0-flash-exp` | Fast classification | $ | Fast |
| `text-embedding-004` | Embeddings | $ | Fast |

### Usage Patterns

```python
# Intent classification (fast model)
response = model.generate_content(
    prompt,
    generation_config={"response_mime_type": "application/json"}
)

# Document parsing (powerful model)
response = model.generate_content(
    f"Extract structured data:\n{pdf_text}",
    generation_config={
        "temperature": 0.1,  # Low for consistency
        "max_output_tokens": 4096
    }
)
```

### Alternative: OpenAI GPT-4

```python
# Pros: Better quality, more community support
# Cons: Higher cost, requires OpenAI account
response = openai.ChatCompletion.create(
    model="gpt-4-turbo",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"}
)
```

---

## Search: Elastic Cloud

### Why Elastic?

**Pros**:
- ✅ **Hybrid Search**: BM25 + kNN in one query
- ✅ **ES|QL**: Powerful SQL-like query language
- ✅ **Aggregations**: Complex analytics queries
- ✅ **Scalability**: Proven at massive scale
- ✅ **Managed Service**: Elastic Cloud handles ops

**Cons**:
- ❌ **Cost**: Can be expensive at scale
- ❌ **Complexity**: Steep learning curve
- ❌ **Java**: JVM memory requirements

### Elastic Features Used

| Feature | Purpose | Example |
|---------|---------|---------|
| **Dense Vector** | Semantic search | kNN with cosine similarity |
| **BM25** | Keyword search | Match on transaction descriptions |
| **ES\|QL** | Analytics | `FROM transactions \| STATS SUM(amount)` |
| **Nested Fields** | Transaction arrays | Query nested statements |
| **Data Streams** | Time-series | Auto-rollover for transactions |

### Index Strategy

```
finsync-transactions (Data Stream)
└─ Backing indices with rollover
   ├─ ds-finsync-transactions-2025.01
   ├─ ds-finsync-transactions-2025.02
   └─ ...

finsync-statements (Index)
└─ Dense vector field (768-dim)
└─ Text fields for keyword search
```

### Alternative: Pinecone

```python
# Pros: Purpose-built for vectors, simpler API
# Cons: No keyword search, no aggregations
import pinecone
index = pinecone.Index("finsync")
results = index.query(vector=embedding, top_k=5)
```

---

## Storage: Google Cloud Storage (GCS)

### Why GCS?

**Pros**:
- ✅ **Durability**: 99.999999999% (11 9's)
- ✅ **GCP Integration**: Native with Cloud Run
- ✅ **Scalability**: Unlimited storage
- ✅ **Lifecycle Policies**: Auto-delete old files
- ✅ **IAM**: Fine-grained access control

**Cons**:
- ❌ **Latency**: Network calls vs local disk
- ❌ **Cost**: $0.02/GB/month (Standard class)

### Storage Classes

| Class | Use Case | Cost | Retrieval |
|-------|----------|------|-----------|
| **Standard** | Frequent access | $0.020/GB | Free |
| **Nearline** | < 1/month | $0.010/GB | $0.01/GB |
| **Coldline** | < 1/quarter | $0.004/GB | $0.02/GB |
| **Archive** | < 1/year | $0.0012/GB | $0.05/GB |

### FinSync Usage

```python
# Development: Local storage
storage = LocalStorage(base_dir="data/uploads")

# Production: GCS
storage = GCSStorage(bucket_name="my-finsync-uploads")

# Unified API
file_path = storage.save_file(file_obj, "statement.pdf")
content = storage.read_file("statement.pdf")
```

---

## Deployment: Cloud Run

### Why Cloud Run?

**Pros**:
- ✅ **Serverless**: Scales to zero (no idle costs)
- ✅ **Container-Based**: Deploy any language/framework
- ✅ **Auto-Scaling**: Handles traffic spikes
- ✅ **Cold Start**: ~1-3 seconds (acceptable for web apps)
- ✅ **Simple**: No k8s complexity

**Cons**:
- ❌ **Stateless**: No local disk persistence
- ❌ **Request Timeout**: Max 60 minutes
- ❌ **WebSocket**: Limited support

### Cloud Run Configuration

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: fin-sync
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"    # Scale to zero
        autoscaling.knative.dev/maxScale: "10"   # Max instances
    spec:
      containers:
      - image: gcr.io/PROJECT/fin-sync
        resources:
          limits:
            memory: 2Gi
            cpu: "2"
        env:
        - name: ENVIRONMENT
          value: production
```

### Alternative: Google App Engine

```yaml
# Pros: Simpler than Cloud Run, fully managed
# Cons: Less flexible, no containers
runtime: python311
entrypoint: streamlit run ui/app.py

env_variables:
  ENVIRONMENT: production
```

---

## CI/CD: Cloud Build

### Why Cloud Build?

**Pros**:
- ✅ **GCP Native**: Integrated with Cloud Run
- ✅ **Docker Support**: Build and deploy containers
- ✅ **Triggers**: Auto-deploy on git push
- ✅ **Free Tier**: 120 build-minutes/day free

**Cons**:
- ❌ **Vendor Lock-in**: GCP-specific
- ❌ **Limited Runners**: Fewer options than GitHub Actions

### Build Configuration

```yaml
# cloudbuild.yaml
steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/fin-sync', '.']
  
  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/fin-sync']
  
  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'fin-sync'
      - '--image=gcr.io/$PROJECT_ID/fin-sync'
      - '--region=us-central1'
```

---

## Secrets Management: Secret Manager

### Why Secret Manager?

**Pros**:
- ✅ **GCP Integration**: Works with Cloud Run
- ✅ **Versioning**: Multiple secret versions
- ✅ **IAM**: Fine-grained access
- ✅ **Audit Logs**: Track secret access

**Usage in FinSync**:

```python
# Production (Cloud Run)
from google.cloud import secretmanager
client = secretmanager.SecretManagerServiceClient()
secret = client.access_secret_version(
    request={"name": f"projects/{PROJECT}/secrets/ELASTIC_API_KEY/versions/latest"}
)
api_key = secret.payload.data.decode("UTF-8")

# Development (Local)
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("ELASTIC_API_KEY")
```

---

## Summary: Decision Matrix

### Choose FinSync Stack When:
- ✅ Building data/AI applications
- ✅ Python expertise
- ✅ GCP infrastructure
- ✅ Need rapid iteration
- ✅ Budget-conscious (serverless)

### Consider Alternatives When:
- ❌ High-traffic consumer app (>100K DAU)
- ❌ Require sub-100ms latency
- ❌ Need complex custom UI
- ❌ Multi-cloud requirement
- ❌ Already invested in AWS/Azure

---

**Related**: [System Overview](./OVERVIEW.md) | [Intent System](./INTENT_SYSTEM.md)

