# Interactive Clarification Flow Documentation

## Overview

The Interactive Clarification Flow is an intelligent system that analyzes user queries and proactively asks for confirmation or clarification when needed. This ensures accurate understanding before executing expensive search and LLM operations.

## Key Features

### 1. **Confidence-Based Confirmation** (≤ 0.75 confidence)
When the system's confidence is low but it has a reasonable understanding, it asks for generic confirmation.

**Example:**
```
User: "show my spending"
System: (Confidence: 70%)
  ⚠️ Please Confirm
  I understood your query as:
  - Intent: Aggregate (sum expenses)
  - Confidence: 70%
  
  Is this what you're looking for?
  [✅ Yes, Continue] [❌ No, Let Me Rephrase]
```

### 2. **Specific Clarification Requests** (needsClarification = true)
When the LLM identifies that specific information is missing, it asks targeted questions.

**Example:**
```
User: "show my bkash transactions"
System: 
  ❓ Need More Information
  🤔 Which time period are you interested in?
  
  Your response: [___________________]
  [Continue] [Skip & Search All]
```

### 3. **Context-Aware Re-classification**
After receiving clarifications, the system reclassifies the intent with full conversation context for better accuracy.

## Workflow States

### State Diagram
```
┌─────────────┐
│    IDLE     │ ← Normal chat mode
└──────┬──────┘
       │ User enters query
       ↓
┌─────────────────┐
│   CLASSIFYING   │ ← Analyzing intent
└──────┬──────────┘
       │
       ├─ High Confidence (>0.75) → SEARCHING
       │
       ├─ Low Confidence (≤0.75) → AWAITING_CONFIRMATION
       │
       └─ Needs Clarification → AWAITING_CLARIFICATION

┌──────────────────────┐
│ AWAITING_CONFIRMATION│
└──────┬───────────────┘
       │
       ├─ User confirms → SEARCHING
       └─ User rejects → IDLE

┌──────────────────────────┐
│ AWAITING_CLARIFICATION   │
└──────┬───────────────────┘
       │
       ├─ User provides clarification → RECLASSIFYING
       └─ User skips → SEARCHING

┌──────────────┐
│RECLASSIFYING │ ← Re-analyzing with context
└──────┬───────┘
       │
       ├─ Still unclear → AWAITING_CLARIFICATION (max 2 times)
       └─ Clear → SEARCHING

┌──────────────┐
│  SEARCHING   │ ← Execute hybrid search
└──────┬───────┘
       ↓
┌──────────────┐
│  GENERATING  │ ← Generate answer
└──────┬───────┘
       ↓
┌──────────────┐
│   COMPLETE   │ → IDLE
└──────────────┘
```

## Session State Management

### New Session State Fields

```python
{
    # Existing fields
    "chat_history": [...],
    
    # NEW: Clarification state
    "pending_query": str | None,          # Query waiting for clarification
    "pending_intent": dict | None,        # Intent awaiting confirmation
    "clarification_mode": str | None,     # "confirm" | "clarify" | None
    "current_conversation": list,         # Conversation context for current query
    "intent_history": list                # Track confidence over time
}
```

### Conversation Context Structure

```python
[
    {
        "type": "query",
        "text": "show my spending",
        "timestamp": "2025-10-24T...",
        "metadata": {"confidence": 0.70, "intent": "aggregate"}
    },
    {
        "type": "clarification_request",
        "text": "Which time period?",
        "timestamp": "2025-10-24T...",
        "metadata": {}
    },
    {
        "type": "clarification_response",
        "text": "Last month",
        "timestamp": "2025-10-24T...",
        "metadata": {}
    }
]
```

## Code Architecture

### Core Components

#### 1. **SessionManager** (`ui/services/session_manager.py`)
Manages all session state including clarification state.

**Key Methods:**
- `get/set_pending_query()` - Manage pending queries
- `get/set_clarification_mode()` - Track current mode
- `add_conversation_turn()` - Add to conversation context
- `get_cumulative_query()` - Build query from context
- `clear_clarification_state()` - Reset everything

#### 2. **ClarificationManager** (`ui/services/clarification_manager.py`)
Business logic for clarification decisions.

**Key Methods:**
- `should_ask_for_confirmation()` - Check if confirmation needed
- `should_ask_for_clarification()` - Check if clarification needed
- `should_proceed_immediately()` - Check if can proceed
- `handle_confirmation_response()` - Process confirmation
- `handle_clarification_input()` - Process clarification

#### 3. **Intent Router** (`llm/intent_router.py`)
Enhanced with context support.

**Key Functions:**
- `classify_intent()` - Base classification (now accepts context)
- `classify_intent_with_context()` - Classification with conversation history
- `classify_intent_safe()` - Safe wrapper

#### 4. **UI Components** (`ui/components/clarification_dialog.py`)
Visual components for clarification interactions.

**Components:**
- `render_confirmation_dialog()` - Confirmation UI
- `render_clarification_dialog()` - Clarification input UI
- `render_conversation_context_display()` - Show conversation history
- `render_clarification_mode_indicator()` - Mode indicator

#### 5. **Chat Page** (`ui/pages/chat_page.py`)
Orchestrates the entire flow.

**Functions:**
- `render()` - Main render function with mode detection
- `_handle_new_query()` - Process new user queries
- `_handle_clarification_interaction()` - Handle clarification UI
- `_proceed_with_search()` - Execute search workflow

## Usage Examples

### Example 1: Low Confidence Query

```python
User Input: "show spending"

Step 1: Intent Classification
  - Intent: aggregate
  - Confidence: 0.68
  - Decision: Ask for confirmation

Step 2: User Interaction
  [Confirmation Dialog Appears]
  User clicks: "✅ Yes, Continue"

Step 3: Proceed with Search
  - Execute hybrid search
  - Generate answer
  - Display results
```

### Example 2: Needs Clarification

```python
User Input: "bkash transactions"

Step 1: Intent Classification
  - Intent: listing
  - Confidence: 0.85
  - Needs Clarification: true
  - Question: "Which time period?"

Step 2: User Interaction
  [Clarification Dialog Appears]
  User types: "last month"
  User clicks: "Continue"

Step 3: Re-classification with Context
  - Cumulative Query: "bkash transactions last month"
  - Context: ["User asked: bkash transactions", "User clarified: last month"]
  - New Intent: listing
  - Confidence: 0.95
  - Decision: Proceed

Step 4: Proceed with Search
  - Execute hybrid search with enhanced query
  - Generate answer
  - Display results
```

### Example 3: Multiple Clarifications

```python
User Input: "show transactions"

Clarification 1:
  System: "Which account?"
  User: "savings"

Clarification 2:
  System: "Which time period?"
  User: "Q3 2024"

Result:
  - Cumulative Query: "show transactions savings Q3 2024"
  - Proceed with search
```

## Configuration

### Thresholds

```python
# In ClarificationManager
CONFIDENCE_THRESHOLD = 0.75       # Below this, ask for confirmation
MAX_CLARIFICATION_ITERATIONS = 2  # Max times to ask for clarification
```

### Customization

To adjust behavior, modify:
- `ClarificationManager.should_ask_for_confirmation()` - Change threshold
- `ClarificationManager.MAX_CLARIFICATION_ITERATIONS` - Change max attempts
- `INTENT_ROUTER_PROMPT` - Adjust LLM instructions

## Error Handling

### Scenarios Handled

1. **Intent Classification Fails**
   - Fallback: Proceed with default search
   - User sees: "Could not classify intent" (warning)

2. **Re-classification Fails**
   - Fallback: Use cumulative query directly
   - Logged as warning

3. **Max Clarification Iterations Reached**
   - Behavior: Proceed with cumulative query anyway
   - Prevents infinite loops

4. **User Abandons Clarification**
   - Behavior: Clear state, return to IDLE
   - User can start fresh query

5. **Session State Corruption**
   - Detection: Check for pending_query without pending_intent
   - Recovery: Clear clarification state, log error

## Performance Considerations

### Additional Latency

- **Confirmation Dialog**: 0ms (no LLM call, UI only)
- **Clarification Dialog**: 0ms (UI only)
- **Re-classification**: 500-2000ms (LLM call with context)

### Token Usage

- **Initial Classification**: 500-1000 tokens
- **Re-classification with Context**: 700-1500 tokens (includes conversation history)

### Optimization Tips

1. **Cache Similar Queries**: Implement query similarity check
2. **Batch Context**: Limit conversation history to last N turns
3. **Smart Defaults**: Learn common clarifications per user
4. **Progressive Enhancement**: Make clarification optional for power users

## Testing

### Manual Test Cases

1. **Test Low Confidence**
   ```
   Query: "spending"
   Expected: Confirmation dialog appears
   Action: Confirm → Search executes
   ```

2. **Test Clarification**
   ```
   Query: "bkash"
   Expected: Clarification dialog asking for time period
   Action: Enter "last month" → Re-classify → Search
   ```

3. **Test Rejection**
   ```
   Query: "show data"
   Expected: Confirmation dialog
   Action: Reject → Return to input, state cleared
   ```

4. **Test Skip**
   ```
   Query: "transactions"
   Expected: Clarification dialog
   Action: Click "Skip" → Search with original query
   ```

5. **Test Multiple Clarifications**
   ```
   Query: "payments"
   Expected: Clarification 1 → Re-classify → Clarification 2 → Search
   ```

### Automated Testing

See `scripts/test_clarification_flow.py` for automated test suite.

## Monitoring & Logging

### Key Metrics

- **Clarification Rate**: % of queries requiring clarification
- **Confirmation Rate**: % of queries requiring confirmation  
- **Rejection Rate**: % of confirmations rejected
- **Re-classification Success**: % of successful re-classifications
- **Average Iterations**: Average clarification rounds per query

### Log Markers

```
INFO: "Entering confirmation mode" - User hit low confidence
INFO: "Entering clarification mode" - Specific info needed
INFO: "User confirmed query" - Confirmation accepted
INFO: "User rejected query" - Confirmation declined
INFO: "Re-classifying with cumulative query" - Context-aware retry
WARNING: "Max clarification iterations reached" - Proceeding anyway
```

## Future Enhancements

1. **Smart Suggestions**: Pre-fill clarification with common answers
2. **Voice Input**: Allow voice clarifications
3. **Multi-turn Dialogs**: Support more complex clarification flows
4. **Learning System**: Learn from user corrections
5. **A/B Testing**: Test different thresholds and prompts
6. **Analytics Dashboard**: Visualize clarification patterns

## Troubleshooting

### Issue: Clarification dialog doesn't appear
**Check:**
- Intent confidence is ≤ 0.75
- `needsClarification` is true
- `clarifyQuestion` is not null

### Issue: Stuck in clarification mode
**Solution:**
- Check `SessionManager.get_clarification_mode()`
- Manually clear: `SessionManager.clear_clarification_state()`
- Check logs for error messages

### Issue: Context not being used
**Check:**
- `current_conversation` has turns
- `classify_intent_with_context()` is being called
- Conversation context is formatted correctly

## Conclusion

The Interactive Clarification Flow significantly improves the system's accuracy and user experience by:
- ✅ Catching misunderstandings early
- ✅ Gathering missing information proactively
- ✅ Using conversation context for better understanding
- ✅ Providing transparency in the AI's reasoning

For implementation details, see the source code in:
- `ui/services/session_manager.py`
- `ui/services/clarification_manager.py`
- `ui/components/clarification_dialog.py`
- `llm/intent_router.py`
- `ui/pages/chat_page.py`

