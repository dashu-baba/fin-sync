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

```bash
# 1. Clone repository
git clone https://github.com/dashu-baba/fin-sync.git
cd fin-sync

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   - GCP_PROJECT_ID
#   - ELASTIC_CLOUD_ENDPOINT
#   - ELASTIC_API_KEY

# 5. Run application
python main.py
# Or directly: streamlit run ui/app.py
```

Access at: `http://localhost:8501`

---

## ⚙️ Configuration

### **Environment Variables**

```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GCS_BUCKET=your-bucket-name  # Optional, for production

# Vertex AI Models
VERTEX_MODEL=gemini-2.0-flash-exp
VERTEX_MODEL_GENAI=gemini-2.0-flash-exp
VERTEX_MODEL_EMBED=text-embedding-004

# Elastic Cloud
ELASTIC_CLOUD_ENDPOINT=https://your-deployment.es.cloud.es.io:443
ELASTIC_API_KEY=your-api-key
ELASTIC_IDX_TRANSACTIONS=finsync-transactions
ELASTIC_IDX_STATEMENTS=finsync-statements
ELASTIC_IDX_AGG_MONTHLY=finsync-aggregates-monthly

# Application
ENVIRONMENT=development  # production | staging | test
LOG_LEVEL=INFO
APP_PORT=8501

# Production Only
USE_SECRET_MANAGER=false  # Set to true in Cloud Run
```

### **Storage Modes**

The app automatically switches storage based on environment:

- **Development**: Local filesystem (`data/uploads/`)
- **Production**: Google Cloud Storage (configured via `GCS_BUCKET`)

Implemented in `core/storage.py` with automatic fallback.

---

## 📁 Project Structure

```
fin-sync/
├── core/                    # Core utilities
│   ├── config.py           # Configuration management
│   ├── logger.py           # Structured logging
│   ├── storage.py          # GCS/Local storage abstraction
│   ├── secrets.py          # Secret Manager integration
│   └── utils.py            # Common utilities
├── elastic/                 # Elastic Cloud integration
│   ├── client.py           # ES client setup
│   ├── indexer.py          # Document indexing
│   ├── search.py           # Hybrid search
│   ├── query_builders.py   # ES|QL query construction
│   ├── executors.py        # Intent execution logic
│   ├── analytics.py        # Analytics queries
│   └── embedding.py        # Vector embedding generation
├── ingestion/               # Document processing
│   ├── pdf_reader.py       # PDF extraction (PyPDF2)
│   └── parser_vertex.py    # Vertex AI parsing
├── llm/                     # LLM integration
│   ├── intent_router.py    # Intent classification
│   ├── intent_executor.py  # Intent-based query execution
│   └── vertex_chat.py      # Gemini chat interface
├── models/                  # Data models
│   ├── schema.py           # Pydantic schemas
│   ├── intent.py           # Intent definitions
│   └── es_docs.py          # Elastic document models
├── ui/                      # Streamlit UI
│   ├── app.py              # Main app entry
│   ├── pages/              # Multi-page app
│   │   ├── Ingest.py       # Upload & parse page
│   │   └── Chat.py         # Conversational interface
│   ├── components/         # Reusable UI components
│   │   ├── upload_form.py
│   │   ├── chat_history.py
│   │   ├── analytics_view.py
│   │   └── intent_display.py
│   └── services/           # Business logic
│       ├── upload_service.py
│       ├── parse_service.py
│       └── clarification_manager.py
├── scripts/                 # Utility scripts
├── docs/                    # Implementation docs
├── Dockerfile              # Container definition
├── cloudbuild.yaml         # CI/CD pipeline
├── deploy.sh               # Deployment script
├── requirements.txt        # Python dependencies
└── main.py                 # Application entry point
```

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
