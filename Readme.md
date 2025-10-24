# 💰 FinSync — AI-Powered Personal Finance Platform

[![Deploy to Cloud Run](https://img.shields.io/badge/Deploy-Cloud%20Run-blue?logo=googlecloud)](https://cloud.google.com/run)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

FinSync is an intelligent personal finance assistant that automatically **parses bank statements**, **analyzes transactions**, and provides **AI-driven insights** about your financial health. Built with **GCP Vertex AI**, **Elastic Cloud**, and **Streamlit**, it offers a conversational interface to understand your spending patterns.

🔗 **Live Demo**: [https://fin-sync-899361706979.us-central1.run.app](https://fin-sync-899361706979.us-central1.run.app)

---

## 🚀 Key Features

### 📄 **Intelligent Document Processing**
- Upload multiple password-protected PDF bank statements
- Automatic extraction using **Gemini 2.5 Pro** (Vertex AI)
- Support for encrypted PDFs with password decryption
- Session-based file management with cleanup

### 🤖 **AI-Powered Intent System**
FinSync uses an advanced **intent classification system** to understand natural language queries:

- **📊 AGGREGATE** - "Show my total spending last month"
- **📊 AGGREGATE_FILTERED_BY_TEXT** - "How much did I spend on groceries?"
- **💬 TEXT_QA** - "What was my biggest transaction?"
- **🔍 PROVENANCE** - "Show me all transactions from IFIC Bank"
- **❓ CLARIFICATION** - Handles ambiguous queries interactively

Each intent uses specialized query strategies (ES|QL aggregations, hybrid search, etc.)

### 🔍 **Hybrid Search with Elastic**
- **Vector embeddings** for semantic search (`text-embedding-004`)
- **Keyword matching** for exact transaction searches
- **ES|QL** for complex aggregations and analytics
- Real-time indexing to Elastic Cloud

### 💬 **Conversational Finance Assistant**
- Natural language interface powered by **Gemini**
- Context-aware responses with source citations
- Multi-turn conversations with clarifications
- Automatic intent routing and query optimization

### 📊 **Interactive Analytics Dashboard**
- Monthly inflow/outflow trends with Plotly
- Transaction distribution by account
- Balance evolution over time
- Account-level filtering and drill-down

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│                    Streamlit (Cloud Run)                     │
└───────┬─────────────────────────┬───────────────────────────┘
        │                         │
        │ Upload PDF              │ Ask Question
        ▼                         ▼
┌───────────────────┐    ┌──────────────────────┐
│   PDF Ingestion   │    │   Intent Router      │
│   • PyPDF2        │    │   • Gemini 2.5 Pro   │
│   • Gemini Parser │    │   • Classification   │
└─────────┬─────────┘    └──────────┬───────────┘
          │                         │
          │ Structured JSON         │ Intent + Parameters
          ▼                         ▼
┌────────────────────────────────────────────────┐
│              Elastic Cloud                     │
│  • finsync-transactions (data stream)         │
│  • finsync-statements (vector index)          │
│  • finsync-aggregates-monthly (rollups)       │
└─────────┬──────────────────────────────────────┘
          │
          │ Results
          ▼
┌──────────────────────────┐
│   Response Generator     │
│   • Gemini with context  │
│   • Source citations     │
└──────────────────────────┘
```

### **Service Interactions**

```
Cloud Run (Streamlit) ──────► Vertex AI (Gemini + Embeddings)
       │
       ├─────────────────────► Elastic Cloud (Hybrid Search)
       │
       └─────────────────────► Cloud Storage (GCS - File Uploads)
       │
       └─────────────────────► Secret Manager (Credentials)
```

---

## 🧱 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Streamlit 1.39 | Interactive UI with chat interface |
| **Backend** | Python 3.11 | Core application logic |
| **LLM** | Gemini 2.5 Pro (Vertex AI) | Document parsing, intent classification, chat |
| **Embeddings** | text-embedding-004 (Vertex AI) | Semantic search vectors (768-dim) |
| **Search & Analytics** | Elastic Cloud 8.15 | Hybrid search, ES\|QL aggregations |
| **Storage** | Local (dev) / GCS (prod) | File storage with automatic switching |
| **Secrets** | GCP Secret Manager | Secure credential management |
| **Deployment** | Cloud Run | Serverless container platform |
| **CI/CD** | Cloud Build | Automated deployments |
| **Logging** | Cloud Logging | Centralized log management |

---

## 📊 Data Model

### **Statement Structure** (Vertex AI Output)
```json
{
  "accountName": "John Doe",
  "accountNo": 123456789,
  "accountType": "Savings",
  "statementFrom": "2025-01-01",
  "statementTo": "2025-01-31",
  "bankName": "ABC Bank",
  "statements": [
    {
      "statementDate": "2025-01-02",
      "statementAmount": 5000.00,
      "statementType": "credit",
      "statementDescription": "Salary Deposit - ABC Corp",
      "statementBalance": 12500.00,
      "statementNotes": "Monthly salary"
    }
  ]
}
```

### **Elastic Indices**

1. **`finsync-transactions`** (Data Stream)
   - Individual transactions with numeric fields
   - Real-time aggregations with ES|QL
   - Time-series optimized

2. **`finsync-statements`** (Vector Index)
   - Statement-level metadata
   - Description embeddings (768-dim)
   - Hybrid search enabled

---

## 🚀 Quick Start

### **Option 1: Cloud Deployment (Recommended)**

Deploy to GCP Cloud Run in 3 steps:

```bash
# 1. Set project
export GCP_PROJECT_ID="your-gcp-project-id"

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Deploy
./deploy.sh
```

Your app will be live at: `https://fin-sync-XXXXX-uc.a.run.app`

See [`QUICKSTART_DEPLOY.md`](QUICKSTART_DEPLOY.md) for detailed deployment guide.

### **Option 2: Local Development**

#### **Prerequisites**
- Python 3.11+
- Google Cloud SDK (for authentication)
- Git

#### **Step-by-Step Setup**

```bash
# 1. Clone repository
git clone https://github.com/dashu-baba/fin-sync.git
cd fin-sync

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up Google Cloud authentication
gcloud auth application-default login
# This creates credentials for Vertex AI access

# 5. Configure environment variables
cp .env.example .env

# Edit .env with your actual values:
# REQUIRED:
#   GCP_PROJECT_ID=your-gcp-project-id
#   ELASTIC_CLOUD_ENDPOINT=https://your-deployment.es.cloud.es.io:443
#   ELASTIC_API_KEY=your-elastic-api-key
#
# OPTIONAL (has defaults):
#   ENVIRONMENT=development
#   LOG_LEVEL=INFO
#   APP_PORT=8501
#   VERTEX_MODEL=gemini-2.0-flash-exp
#   VERTEX_MODEL_EMBED=text-embedding-004

# 6. Run the application
python main.py
```

**Alternative run methods:**
```bash
# Direct Streamlit run
streamlit run ui/app.py --server.port 8501

# With custom port
python main.py  # Uses PORT from .env or default 8501
```

**Access the app at**: `http://localhost:8501`

#### **What Happens on First Run**

1. **Directory Creation**: `data/uploads/` and `data/output/` folders are auto-created
2. **Elastic Indices**: Automatically created on first document upload
3. **Logs**: Written to `data/output/app.log` and console
4. **Storage**: Files stored locally in `data/uploads/` (development mode)

#### **Testing Local Setup**

```bash
# Verify Python version
python --version  # Should be 3.11+

# Check installed packages
pip list | grep -E "streamlit|google-cloud|elastic"

# Test Vertex AI connection
python -c "from google.cloud import aiplatform; print('Vertex AI SDK loaded')"

# Test Elastic connection (after setting .env)
python -c "from elastic.client import get_client; print('Elastic client OK')"
```

---

## ⚙️ Configuration

### **Environment Variables**

Copy `.env.example` and configure with your values:

```bash
# Environment Configuration
ENVIRONMENT=development                # development | production | staging | test
LOG_LEVEL=INFO                        # DEBUG | INFO | WARNING | ERROR
APP_PORT=8501                         # Port for Streamlit app

# GCP Configuration (REQUIRED)
GCP_PROJECT_ID=your-gcp-project-id    # Your Google Cloud project ID
GCP_LOCATION=us-central1              # GCP region for Vertex AI
GCS_BUCKET=your-project-finsync-uploads  # GCS bucket (optional, for production)

# Vertex AI Models
VERTEX_MODEL=gemini-2.0-flash-exp           # Model for parsing & chat
VERTEX_MODEL_GENAI=gemini-2.0-flash-exp     # Generative AI model
VERTEX_MODEL_EMBED=text-embedding-004       # Embedding model (768-dim)

# Elastic Cloud Configuration (REQUIRED)
ELASTIC_CLOUD_ENDPOINT=https://your-deployment.es.cloud.es.io:443
ELASTIC_API_KEY=your-elastic-api-key
ELASTIC_INDEX_NAME=finsync-transactions          # Legacy index name
ELASTIC_IDX_TRANSACTIONS=finsync-transactions    # Transaction data stream
ELASTIC_IDX_STATEMENTS=finsync-statements        # Statement vector index
ELASTIC_IDX_AGG_MONTHLY=finsync-aggregates-monthly  # Monthly rollup index
ELASTIC_TXN_MONTHLY_TRANSFORM_ID=finsync_txn_monthly  # Transform ID
ELASTIC_ALIAS_TXN_VIEW=finsync-transactions-view     # Transaction alias

# Elastic Vector Configuration
ELASTIC_VECTOR_FIELD=desc_vector      # Field name for embeddings
ELASTIC_VECTOR_DIM=768                # Embedding dimensions

# Production Only (Cloud Run)
USE_SECRET_MANAGER=false              # Set to true in Cloud Run
```

**Required for Local Development:**
- `GCP_PROJECT_ID` - Your GCP project with Vertex AI enabled
- `ELASTIC_CLOUD_ENDPOINT` - Your Elastic Cloud deployment URL
- `ELASTIC_API_KEY` - Elastic Cloud API key

**Optional (has sensible defaults):**
- All other variables have default values and can be omitted

### **Storage Modes**

The app automatically switches storage based on environment:

- **Development**: Local filesystem (`data/uploads/`)
- **Production**: Google Cloud Storage (configured via `GCS_BUCKET`)

Implemented in `core/storage.py` with automatic fallback.

---

## 📁 Project Structure

```
fin-sync/
├── core/                          # Core utilities & configuration
│   ├── __init__.py
│   ├── config.py                 # Environment & settings management
│   ├── logger.py                 # Structured logging (loguru)
│   ├── storage.py                # GCS/Local storage abstraction
│   ├── secrets.py                # GCP Secret Manager integration
│   └── utils.py                  # Common helper functions
│
├── elastic/                       # Elastic Cloud integration
│   ├── __init__.py
│   ├── analytics.py              # ES|QL analytics queries
│   ├── client.py                 # Elasticsearch client setup
│   ├── embedding.py              # Vertex AI embedding generation
│   ├── executors.py              # Intent query executors
│   ├── indexer.py                # Document indexing & ingestion
│   ├── mappings.py               # Index mappings & schemas
│   ├── prompts.py                # LLM prompts for search
│   ├── query_builders.py         # ES|QL query construction
│   ├── search.py                 # Hybrid search implementation
│   └── transforms.py             # Data transforms for rollups
│
├── ingestion/                     # PDF processing & parsing
│   ├── __init__.py
│   ├── pdf_reader.py             # PDF extraction (PyPDF2)
│   └── parser_vertex.py          # Vertex AI statement parser
│
├── llm/                           # Large Language Model integration
│   ├── __init__.py
│   ├── intent_executor.py        # Execute classified intents
│   ├── intent_router.py          # Intent classification system
│   └── vertex_chat.py            # Gemini chat interface
│
├── models/                        # Data models & schemas
│   ├── __init__.py
│   ├── es_docs.py                # Elasticsearch document models
│   ├── intent.py                 # Intent type definitions
│   └── schema.py                 # Pydantic schemas
│
├── ui/                            # Streamlit user interface
│   ├── app.py                    # Main Streamlit app entry
│   │
│   ├── components/               # Reusable UI components
│   │   ├── analytics_view.py    # Analytics dashboard
│   │   ├── chat_history.py      # Chat conversation display
│   │   ├── clarification_dialog.py  # Clarification UI
│   │   ├── file_list.py         # Uploaded files list
│   │   ├── filter_bar.py        # Analytics filters
│   │   ├── intent_display.py    # Intent classification display
│   │   ├── intent_results.py    # Query results display
│   │   ├── parse_section.py     # Parse status section
│   │   ├── sidebar.py           # Sidebar navigation
│   │   └── upload_form.py       # File upload form
│   │
│   ├── config/                   # UI configuration
│   │   └── page_config.py       # Streamlit page config
│   │
│   ├── pages/                    # Multi-page app pages
│   │   ├── Chat.py              # Chat interface page
│   │   └── Ingest.py            # Upload & parse page
│   │
│   ├── services/                 # Business logic services
│   │   ├── clarification_manager.py  # Clarification flow
│   │   ├── parse_service.py     # PDF parsing service
│   │   ├── session_manager.py   # Session state management
│   │   └── upload_service.py    # File upload handling
│   │
│   └── views/                    # Page view logic
│       ├── analytics_page.py    # Analytics page logic
│       ├── chat_page.py         # Chat page logic
│       └── ingest_page.py       # Ingest page logic
│
├── scripts/                       # Utility & testing scripts
│   ├── check_embedding_dim.py
│   ├── fix_indices.py
│   ├── test_aggregate_intent.py
│   ├── test_intent_router.py
│   ├── verify_aggregate_filtered_by_text_structure.py
│   ├── verify_aggregate_structure.py
│   ├── verify_provenance_structure.py
│   └── verify_text_qa_structure.py
│
├── data/                          # Local data (not in git)
│   ├── uploads/                  # Uploaded PDFs (session-based)
│   └── output/                   # Logs & outputs
│       └── app.log              # Application logs
│
├── docs/                          # Implementation documentation
│   ├── AGGREGATE_FILTERED_BY_TEXT_IMPLEMENTATION.md
│   ├── AGGREGATE_INTENT_IMPLEMENTATION.md
│   ├── CLARIFICATION_FLOW.md
│   ├── CLARIFICATION_IMPLEMENTATION_SUMMARY.md
│   ├── COMPLETE_INTENT_SYSTEM.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── INTENT_CLASSIFICATION.md
│   ├── PROVENANCE_INTENT_IMPLEMENTATION.md
│   └── TEXT_QA_INTENT_IMPLEMENTATION.md
│
├── .github/                       # GitHub workflows
│   └── workflows/
│       └── deploy.yml            # GitHub Actions CI/CD
│
├── main.py                        # Application entry point
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
│
├── Dockerfile                     # Docker container definition
├── .dockerignore                  # Docker ignore rules
├── cloudbuild.yaml                # Cloud Build CI/CD config
│
├── deploy.sh                      # GCP deployment script
├── setup-cicd.sh                  # CI/CD setup script
│
├── DEPLOYMENT.md                  # Complete deployment guide
├── DEPLOYMENT_SUMMARY.md          # Deployment overview
├── QUICKSTART_DEPLOY.md           # Quick deployment reference
├── CICD_SETUP.md                  # CI/CD automation guide
├── TODO_DEPLOYMENT.md             # GCS integration checklist
├── SECURITY_AUDIT.md              # Security audit report
├── INTEGRATION_CHECKLIST.md       # Integration checklist
│
└── Readme.md                      # This file
```

**Key Directories:**
- **`core/`** - Configuration, logging, storage, secrets
- **`elastic/`** - All Elasticsearch/Elastic Cloud functionality
- **`ingestion/`** - PDF parsing with Vertex AI
- **`llm/`** - Intent routing & Gemini integration
- **`models/`** - Pydantic schemas & data models
- **`ui/`** - Complete Streamlit application
- **`scripts/`** - Testing & verification utilities
- **`docs/`** - Detailed implementation docs

---

## 🎯 Intent System

FinSync uses a sophisticated intent classification system to route user queries:

### **Supported Intents**

| Intent | Description | Example Query |
|--------|-------------|---------------|
| `AGGREGATE` | Numeric aggregations | "Total spending in June" |
| `AGGREGATE_FILTERED_BY_TEXT` | Text-filtered aggregations | "How much spent on food?" |
| `TEXT_QA` | Question answering | "What was my largest expense?" |
| `PROVENANCE` | Source/metadata queries | "Show transactions from IFIC Bank" |
| `CLARIFICATION` | Ambiguous queries | "Show my expenses" (Which month?) |

### **Intent Flow**

1. **Classification**: Gemini analyzes query → determines intent
2. **Parameter Extraction**: Extracts entities (dates, amounts, keywords)
3. **Execution**: Runs specialized ES|QL or hybrid search query
4. **Response Generation**: Gemini generates natural language response with citations

See [`docs/COMPLETE_INTENT_SYSTEM.md`](docs/COMPLETE_INTENT_SYSTEM.md) for details.

---

## 🔒 Security Best Practices

- ✅ **Secret Management**: Credentials stored in GCP Secret Manager (production)
- ✅ **HTTPS Only**: All traffic encrypted via Cloud Run
- ✅ **Container Security**: Minimal base image, regular updates
- ✅ **IAM Roles**: Least-privilege service accounts
- ✅ **No Hardcoded Secrets**: Environment-based configuration
- ✅ **Session Isolation**: User uploads isolated in session directories
- ✅ **PDF Encryption Support**: Handles password-protected documents

---

## 🚀 Deployment

### **Manual Deployment**

```bash
# Deploy to Cloud Run
gcloud run deploy fin-sync \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --set-env-vars ENVIRONMENT=production
```

### **Automated CI/CD**

**Cloud Build Trigger** (Recommended):
1. Connect GitHub repository in Cloud Console
2. Create trigger on `main` branch
3. Every push auto-deploys

See [`CICD_SETUP.md`](CICD_SETUP.md) for complete setup guide.

### **GitHub Actions**

Workflow included at `.github/workflows/deploy.yml` for GitHub-based CI/CD.

---

## 📈 Monitoring & Observability

### **View Logs**
```bash
# Real-time logs
gcloud run services logs tail fin-sync --region=us-central1

# Recent logs
gcloud run services logs read fin-sync --limit=100
```

### **Cloud Console**
- **Logs**: https://console.cloud.google.com/run/detail/us-central1/fin-sync/logs
- **Metrics**: https://console.cloud.google.com/run/detail/us-central1/fin-sync/metrics
- **Builds**: https://console.cloud.google.com/cloud-build/builds

### **Application Health**
```bash
curl https://YOUR-SERVICE-URL/_stcore/health
```

---

## 💰 Cost Optimization

| Service | Usage | Est. Cost/Month |
|---------|-------|-----------------|
| Cloud Run | 10K requests | ~$5 |
| Vertex AI (Gemini) | 1M tokens | ~$10-20 |
| Vertex AI (Embeddings) | 100K texts | ~$2 |
| Cloud Storage | 10GB | $0.20 |
| Secret Manager | 3 secrets | $0.18 |
| Elastic Cloud | Managed service | Varies |
| **Total (GCP)** | | **~$15-25/mo** |

**Optimization Tips**:
- Cloud Run scales to zero (no idle costs)
- Use `gemini-2.0-flash-exp` for lower costs
- Enable response caching for repeated queries
- Set up lifecycle policies on GCS

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Test intent classification
python scripts/test_intent_router.py

# Test aggregate queries
python scripts/test_aggregate_intent.py

# Verify index structure
python scripts/verify_aggregate_structure.py
```

---

## 📚 Documentation

- [`DEPLOYMENT.md`](DEPLOYMENT.md) - Complete deployment guide
- [`QUICKSTART_DEPLOY.md`](QUICKSTART_DEPLOY.md) - Quick deployment reference
- [`CICD_SETUP.md`](CICD_SETUP.md) - CI/CD automation setup
- [`TODO_DEPLOYMENT.md`](TODO_DEPLOYMENT.md) - GCS integration checklist
- [`docs/COMPLETE_INTENT_SYSTEM.md`](docs/COMPLETE_INTENT_SYSTEM.md) - Intent system architecture
- [`docs/AGGREGATE_INTENT_IMPLEMENTATION.md`](docs/AGGREGATE_INTENT_IMPLEMENTATION.md) - Aggregation queries
- [`docs/TEXT_QA_INTENT_IMPLEMENTATION.md`](docs/TEXT_QA_INTENT_IMPLEMENTATION.md) - QA system

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Cloud Platform** - Vertex AI, Cloud Run
- **Elastic** - Elastic Cloud, ES|QL
- **Streamlit** - Interactive UI framework
- **PyPDF2** - PDF parsing library

---

## 📧 Contact

**Project Link**: [https://github.com/dashu-baba/fin-sync](https://github.com/dashu-baba/fin-sync)

**Issues**: [https://github.com/dashu-baba/fin-sync/issues](https://github.com/dashu-baba/fin-sync/issues)

---

## 🗺️ Roadmap

- [ ] Multi-user authentication with Firebase Auth
- [ ] Budget tracking and alerts
- [ ] Spending category auto-tagging with ML
- [ ] Export reports (PDF, Excel)
- [ ] Mobile app (Flutter)
- [ ] Integration with bank APIs (Plaid)
- [ ] Predictive cash flow analysis
- [ ] Bill payment reminders
- [ ] Investment portfolio tracking

---

**Built with ❤️ using GCP, Elastic, and Streamlit**
