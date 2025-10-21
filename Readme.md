# 💰 FinSync — Personal Fintech Care Platform

FinSync is a smart personal finance assistant that lets users **upload their bank statements**, automatically **parse and analyze transactions**, and get **AI-driven insights** about spending patterns, savings, and financial health.  
It combines the power of **GCP Vertex AI**, **ElasticSearch hybrid search**, and **Streamlit** for an intelligent and interactive experience.

---

## 🚀 Key Features

- 🏦 **Secure Bank Statement Upload**  
  Supports uploading multiple password-protected statements (PDF).  

- 🧠 **AI-Powered Parsing (GCP Vertex AI)**  
  Extracts structured financial data as JSON with fields like account details, transaction types, balances, and notes.

- 🧩 **Hybrid Search with Elastic**  
  Embeds text fields for semantic + numeric hybrid search using Elastic.co’s vector and keyword indexing.

- 💬 **Conversational Finance Assistant**  
  Uses Vertex AI Generative models for chat-based Q&A about your statements — “What was my biggest expense in July?”  

- 📊 **Interactive Dashboard (Streamlit)**  
  Visualizes spending habits, cash inflows/outflows, and balance trends interactively.

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|-------------|
| **Frontend/UI** | Streamlit |
| **Backend** | Python (FastAPI optional) |
| **AI/ML** | Google Vertex AI |
| **Search Engine** | ElasticSearch (hybrid search: dense + sparse embeddings) |
| **Storage** | GCS (Google Cloud Storage) |
| **Embedding Model** | Vertex AI Text Embedding API |
| **Auth** | Google OAuth / Custom Token Auth |

---

## 🧩 Data Structure

Each uploaded statement is parsed into a structured JSON:

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
      "statementAmount": 5000,
      "statementType": "credit",
      "statementDescription": "Salary Deposit",
      "statementBalance": 7500
    }
  ]
}


