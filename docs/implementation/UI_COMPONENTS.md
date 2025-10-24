# UI Components & Services

Streamlit-based user interface architecture with component-based design.

---

## Structure

```
ui/
├── app.py                      # Main app entry point
├── config/
│   └── page_config.py          # Streamlit page configuration
├── pages/
│   ├── Chat.py                 # Chat interface page
│   └── Ingest.py               # Upload & parse page
├── components/
│   ├── analytics_view.py       # Analytics charts
│   ├── chat_history.py         # Chat conversation display
│   ├── clarification_dialog.py # Clarification UI
│   ├── intent_display.py       # Intent classification display
│   ├── intent_results.py       # Query results display
│   ├── upload_form.py          # File upload form
│   └── uploaded_files_display.py # File list display
├── services/
│   ├── clarification_manager.py # Clarification logic
│   ├── parse_service.py        # PDF parsing service
│   ├── session_manager.py      # Session state management
│   └── upload_service.py       # File upload handling
└── views/
    ├── analytics_page.py       # Analytics page logic
    ├── chat_page.py            # Chat page logic
    └── ingest_page.py          # Ingest page logic
```

---

## Key Patterns

### 1. Component Pattern

**Reusable UI components** that render specific sections:

```python
# ui/components/intent_display.py

def render_intent_display(intent_response: IntentResponse):
    """Render intent classification results."""
    with st.expander("🎯 Intent Classification", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"**Intent**: {intent_response.classification.intent}")
            st.write(f"**Confidence**: {intent_response.classification.confidence:.0%}")
        
        with col2:
            st.metric("Processing Time", f"{intent_response.processing_time_ms}ms")
```

### 2. Service Pattern

**Business logic** separated from UI:

```python
# ui/services/upload_service.py

class UploadService:
    @staticmethod
    def process_upload(
        file: UploadedFile,
        upload_dir: Path,
        password: str | None = None
    ) -> dict:
        """Process uploaded file."""
        # 1. Check duplicates
        # 2. Save file
        # 3. Extract text
        # 4. Parse with Vertex AI
        # 5. Index to Elastic
        return {"status": "success", "data": parsed}
```

### 3. View Pattern

**Page rendering logic** orchestrates components and services:

```python
# ui/views/chat_page.py

def render():
    """Render chat page."""
    # Load services
    from ui.services.session_manager import SessionManager
    from llm.intent_router import classify_intent
    
    # Render components
    render_chat_history()
    
    # Handle user input
    if query := st.chat_input("Ask a question..."):
        # Classify intent
        intent = classify_intent(query)
        
        # Execute
        result = execute_intent(query, intent)
        
        # Display
        render_intent_results(result)
```

---

## Session State Management

**Centralized session state**:

```python
# ui/services/session_manager.py

class SessionManager:
    @staticmethod
    def initialize():
        """Initialize all session state variables."""
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "uploaded_files" not in st.session_state:
            st.session_state.uploaded_files = []
        # ... more state
    
    @staticmethod
    def add_message(role: str, content: str):
        """Add message to chat history."""
        st.session_state.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })
```

---

## Key Components

### Upload Form
**Purpose**: File upload with validation  
**File**: `ui/components/upload_form.py`

### Chat History
**Purpose**: Display conversation  
**File**: `ui/components/chat_history.py`

### Intent Display
**Purpose**: Show classification results  
**File**: `ui/components/intent_display.py`

### Clarification Dialog
**Purpose**: Interactive clarification  
**File**: `ui/components/clarification_dialog.py`

### Analytics View
**Purpose**: Financial dashboards  
**File**: `ui/components/analytics_view.py`

---

## Best Practices

✅ **Componentize**: Reusable UI functions  
✅ **Separate logic**: Services handle business logic  
✅ **Cache data**: `@st.cache_data` for expensive ops  
✅ **Session state**: Centralized state management  
❌ **Don't mix concerns**: Keep UI and logic separate

---

**Related**: [Analytics](../features/ANALYTICS.md) | [Clarification Flow](../features/CLARIFICATION_FLOW.md)

