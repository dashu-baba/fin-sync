# FinSync Documentation

**Welcome to the FinSync documentation!** This guide provides comprehensive information about the AI-powered personal finance platform built with GCP Vertex AI, Elastic Cloud, and Streamlit.

---

## 🆕 What's New

**[Recent Changes & Updates](./RECENT_CHANGES.md)** - Latest bug fixes, features, and improvements

Recent highlights:
- ✅ **Query matching fix** (Oct 24, 2025) - Fixed `aggregate_filtered_by_text` returning 0 for valid queries
- ✅ **Automatic file cleanup** on upload failures
- 🗑️ **Manual file deletion** in UI
- 🔧 **Optional schema fields** for better robustness
- 📄 **Enhanced PDF parsing** with improved prompts

**Critical Fix**: If you're getting 0 results for queries like "How much did I spend on X?", see [AGGREGATE_FILTERED_BY_TEXT_FIX.md](./AGGREGATE_FILTERED_BY_TEXT_FIX.md)

---

## 📚 Documentation Structure

### 🏗️ [Architecture](./architecture/)
Understanding the system design, data flow, and technical decisions.

- **[System Overview](./architecture/OVERVIEW.md)** - High-level architecture and components
- **[Data Flow](./architecture/DATA_FLOW.md)** - How data moves through the system
- **[Tech Stack](./architecture/TECH_STACK.md)** - Technology choices and rationale
- **[Intent System](./architecture/INTENT_SYSTEM.md)** - Intent classification architecture

### ✨ [Features](./features/)
User-facing features and capabilities.

- **[Document Processing](./features/DOCUMENT_PROCESSING.md)** - PDF parsing with Vertex AI
- **[Intent Classification](./features/INTENT_CLASSIFICATION.md)** - Natural language understanding
- **[Hybrid Search](./features/HYBRID_SEARCH.md)** - Semantic + keyword search
- **[Analytics Dashboard](./features/ANALYTICS.md)** - Financial insights and visualizations
- **[Clarification Flow](./features/CLARIFICATION_FLOW.md)** - Interactive query refinement
- **[Duplicate Protection](./features/DUPLICATE_PROTECTION.md)** - Multi-layer duplicate detection
- **[UI/UX Improvements](./UI_IMPROVEMENTS.md)** - Plain English confirmations, flexible matching, debug mode

### 🔧 [Implementation](./implementation/)
Technical implementation details and code organization.

- **[Core Modules](./implementation/CORE_MODULES.md)** - Configuration, logging, utilities
- **[Elastic Integration](./implementation/ELASTIC_INTEGRATION.md)** - Search, indexing, analytics
- **[LLM Integration](./implementation/LLM_INTEGRATION.md)** - Vertex AI usage patterns
- **[Storage Backend](./implementation/STORAGE_BACKEND.md)** - Local/GCS abstraction
- **[UI Components](./implementation/UI_COMPONENTS.md)** - Streamlit components and services

### 🚀 [Deployment](./deployment/)
Deploying FinSync to production.

- **[Quick Start](./deployment/QUICKSTART.md)** - Get deployed in 5 minutes
- **[GCP Deployment](./deployment/GCP_DEPLOYMENT.md)** - Complete Cloud Run setup
- **[CI/CD Setup](./deployment/CICD_SETUP.md)** - Automated deployments
- **[Configuration](./deployment/CONFIGURATION.md)** - Environment variables and secrets

### 💻 [Development](./development/)
Developer guides and references.

- **[Local Setup](./development/SETUP.md)** - Development environment setup
- **[API Reference](./development/API_REFERENCE.md)** - Key functions and classes
- **[Testing](./development/TESTING.md)** - Testing strategies and scripts
- **[Contributing](./development/CONTRIBUTING.md)** - Contribution guidelines

---

## 🚀 Quick Links

### For New Users
1. Start with [System Overview](./architecture/OVERVIEW.md) to understand the architecture
2. Read [Quick Start](./deployment/QUICKSTART.md) to deploy your own instance
3. Explore [Features](./features/) to see what the system can do

### For Developers
1. Follow [Local Setup](./development/SETUP.md) to get started
2. Review [API Reference](./development/API_REFERENCE.md) for code documentation
3. Check [Implementation](./implementation/) for technical details

### For DevOps
1. Read [GCP Deployment](./deployment/GCP_DEPLOYMENT.md) for infrastructure
2. Configure [CI/CD](./deployment/CICD_SETUP.md) for automation
3. Review [Configuration](./deployment/CONFIGURATION.md) for all settings

---

## 📖 Documentation Conventions

### Code Examples
All code examples are tested and working. They use:
- **Python 3.11+** syntax
- **Type hints** for clarity
- **Async/await** where appropriate

### Environment Variables
Format: `VARIABLE_NAME=value` with descriptions inline.

### Paths
- **Absolute paths** for clarity: `/Users/.../fin-sync/...`
- **Relative paths** from project root: `docs/`, `core/`, etc.

### Status Indicators
- ✅ **Complete** - Fully implemented and tested
- 🚧 **In Progress** - Partially implemented
- 📝 **Planned** - Documented but not yet built

---

## 🔄 Recent Updates

**October 24, 2025**
- 📚 Major documentation reorganization
- 🏗️ Added architecture diagrams and explanations
- ✨ Documented all features comprehensively
- 🔧 Added implementation guides
- 🚀 Updated deployment documentation

---

## 🤝 Contributing to Docs

Found an error or want to improve the docs?

1. **Edit the file** - All docs are Markdown in the `docs/` folder
2. **Follow the structure** - Use existing format and sections
3. **Test examples** - Ensure code examples work
4. **Submit PR** - Open a pull request with your changes

See [Contributing Guide](./development/CONTRIBUTING.md) for details.

---

## 📧 Getting Help

- **Issues**: [GitHub Issues](https://github.com/dashu-baba/fin-sync/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dashu-baba/fin-sync/discussions)
- **Email**: Contact through GitHub profile

---

**Last Updated**: October 24, 2025  
**Version**: 1.0  
**Status**: ✅ Complete

