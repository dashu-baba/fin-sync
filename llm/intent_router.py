"""Intent classification router using Vertex AI."""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from typing import Optional

from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.cloud import aiplatform

from core.config import config as cfg
from core.logger import get_logger
from models.intent import IntentClassification, IntentResponse

log = get_logger("llm/intent_router")


# Intent classification system prompt
INTENT_ROUTER_PROMPT = """You are the FinSync Intent Router. 
Your ONLY job is to classify a user's finance query and emit a strict JSON plan.
Do NOT answer the question. Do NOT compute numbers. Do NOT invent fields.

### Time & Locale
- Current date: {current_date}
- User timezone: Asia/Dhaka (UTC+06:00)
- Resolve relative dates into ISO-8601 (YYYY-MM-DD).

### Data Sources
1) transactions (Elastic data stream): numeric aggregations, trends, counts, group-bys.
2) statements (Elastic index, BM25+vector): semantic text Q&A and provenance.

### Intent Types (choose exactly one)
- "aggregate": totals, sums, counts, averages, trends, top-N; numeric answers from transactions.
- "text_qa": explain/define/describe something from statements; no numbers needed.
- "aggregate_filtered_by_text": need statements to find a subset (e.g., merchants, concepts) then aggregate those matching transactions.
- "listing": a tabular list of transactions or entities (e.g., "show last 10 bkash transactions").
- "trend": explicitly time-series trend (monthly, weekly, daily) of income/expense/net.
- "provenance": user asks for source evidence/citations (pages, statementId).

### Field Extraction Rules
- filters:
  - accountNo (exact if present)
  - dateFrom / dateTo (resolve "last 2 months", "this year", "Q3 2024" → exact dates)
  - counterparty (merchant/payee keywords like "bkash", "uber")
  - minAmount / maxAmount when specified (>=, <=, "more than", "under")
- metrics (subset of):
  ["sum_income","sum_expense","net","count","avg","top_merchants","top_categories","monthly_trend","weekly_trend","daily_trend"]
- granularity: "daily" | "weekly" | "monthly" (default monthly)
- needsTable: true if the user asks to "list" or will benefit from a compact table
- answerStyle: "concise" | "detailed" (infer from wording)
- confidence: 0.0–1.0. If <0.6 set needsClarification=true and include clarifyQuestion.

### Decision Heuristics
- If the user asks "total/average/count/top/trend" → aggregate (or trend if time-series emphasized).
- If the user asks "what is/describe/explain/which page shows" → text_qa.
- If the user asks a total **for a named concept** that must be discovered in statements (e.g., "all fees mentioned", "bkash spend if it appears in statements") → aggregate_filtered_by_text.
- If the user says "show/list" of transactions → listing (transactions). If list of pages/snippets → text_qa.
- If user requests citations/sources/pages → provenance (and set provenance=true).
- If ambiguous merchant-like token (e.g., "bkash") with an explicit total → aggregate; BUT if you cannot be sure it's a transactions merchant without confirming via statements, prefer aggregate_filtered_by_text with confidence lowered to 0.65–0.75.

### Guardrails
- OUTPUT ONLY JSON. No prose. No equations. No chain-of-thought.
- Never fabricate account numbers or dates.
- Prefer narrower filters when user specifies any.
- For "last N months/weeks/days", set dateTo to today and backfill dateFrom accordingly.

Return JSON matching this schema:
{{
  "intent": "aggregate" | "text_qa" | "aggregate_filtered_by_text" | "listing" | "trend" | "provenance",
  "filters": {{
    "accountNo": string | null,
    "dateFrom": "YYYY-MM-DD" | null,
    "dateTo": "YYYY-MM-DD" | null,
    "counterparty": string | null,
    "minAmount": number | null,
    "maxAmount": number | null
  }},
  "metrics": ["sum_income", "sum_expense", "net", "count", "avg", "top_merchants", "top_categories", "monthly_trend", "weekly_trend", "daily_trend"],
  "granularity": "daily" | "weekly" | "monthly",
  "needsTable": boolean,
  "answerStyle": "concise" | "detailed",
  "confidence": number (0.0-1.0),
  "needsClarification": boolean,
  "clarifyQuestion": string | null,
  "provenance": boolean,
  "reasoning": string | null
}}

ONLY output valid JSON. No markdown, no backticks, no explanation."""


def _init_vertex() -> None:
    """Initialize Vertex AI client."""
    if not hasattr(_init_vertex, "_initialized"):
        log.info(f"Initializing Vertex AI: project={cfg.gcp_project_id}, location={cfg.gcp_location}")
        aiplatform.init(project=cfg.gcp_project_id, location=cfg.gcp_location)
        _init_vertex._initialized = True


def _extract_json_from_response(text: str) -> str:
    """
    Extract JSON from LLM response, handling markdown code blocks.
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Cleaned JSON string
    """
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```"):
        # Find the first newline after ```
        start = text.find('\n')
        if start != -1:
            text = text[start + 1:]
        # Remove trailing ```
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    
    # Remove "json" language identifier if present
    if text.startswith("json\n"):
        text = text[5:]
    
    return text.strip()


def classify_intent(
    query: str,
    current_date: Optional[str] = None,
    conversation_context: Optional[str] = None
) -> IntentResponse:
    """
    Classify user intent using Vertex AI.
    
    Args:
        query: User's financial query
        current_date: Current date in YYYY-MM-DD format (defaults to today)
        conversation_context: Optional previous conversation context for better understanding
        
    Returns:
        IntentResponse with classification results
        
    Raises:
        Exception: If LLM call or JSON parsing fails
    """
    start_time = time.time()
    
    # Get current date if not provided
    if current_date is None:
        current_date = datetime.now(timezone.utc).date().isoformat()
    
    log.info(f"Classifying intent for query: '{query}' (date: {current_date})")
    
    try:
        # Initialize Vertex AI
        _init_vertex()
        
        # Create model with JSON mode
        model = GenerativeModel(cfg.vertex_model_genai)
        
        # Format the prompt with current date
        system_prompt = INTENT_ROUTER_PROMPT.format(current_date=current_date)
        
        # Build user prompt with optional context
        user_prompt_parts = []
        
        if conversation_context:
            user_prompt_parts.append(conversation_context)
            log.debug("Including conversation context in classification")
        
        user_prompt_parts.append(f"\nCurrent User Query: {query}")
        user_prompt = "\n".join(user_prompt_parts)
        
        # Generate with strict JSON output
        generation_config = GenerationConfig(
            temperature=0.0,  # Deterministic output
            max_output_tokens=2048,
        )
        
        log.debug(f"Sending query to Vertex AI: {cfg.vertex_model_genai}")
        
        # Call LLM
        response = model.generate_content(
            [system_prompt, user_prompt],
            generation_config=generation_config
        )
        
        # Extract response text
        response_text = (response.text or "").strip()
        
        if not response_text:
            log.error("Empty response from Vertex AI")
            raise ValueError("Empty response from LLM")
        
        log.debug(f"Raw LLM response: {response_text[:500]}...")
        
        # Extract JSON from response (handle markdown)
        json_text = _extract_json_from_response(response_text)
        
        # Parse JSON
        try:
            intent_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON response: {e}\nResponse: {json_text}")
            raise ValueError(f"Invalid JSON from LLM: {e}")
        
        # Validate with Pydantic
        classification = IntentClassification(**intent_data)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Create response
        intent_response = IntentResponse(
            query=query,
            classification=classification,
            timestamp=datetime.now(timezone.utc).isoformat(),
            processing_time_ms=round(processing_time, 2)
        )
        
        log.info(
            f"Intent classified successfully: intent={classification.intent}, "
            f"confidence={classification.confidence}, time={processing_time:.0f}ms"
        )
        
        return intent_response
        
    except Exception as e:
        log.exception(f"Intent classification failed for query '{query}': {e}")
        raise


def classify_intent_safe(
    query: str,
    current_date: Optional[str] = None,
    conversation_context: Optional[str] = None
) -> Optional[IntentResponse]:
    """
    Safely classify user intent, returning None on failure.
    
    Args:
        query: User's financial query
        current_date: Current date in YYYY-MM-DD format
        conversation_context: Optional previous conversation context
        
    Returns:
        IntentResponse or None if classification fails
    """
    try:
        return classify_intent(query, current_date, conversation_context)
    except Exception as e:
        log.error(f"Intent classification failed (safe mode): {e}")
        return None


def classify_intent_with_context(
    query: str,
    conversation_turns: list,
    current_date: Optional[str] = None
) -> Optional[IntentResponse]:
    """
    Classify intent with full conversation context.
    
    Args:
        query: Current user query
        conversation_turns: List of previous conversation turns
        current_date: Current date in YYYY-MM-DD format
        
    Returns:
        IntentResponse or None if classification fails
    """
    # Build context string from conversation turns
    context_lines = []
    
    if conversation_turns:
        context_lines.append("### Previous Conversation:")
        for turn in conversation_turns:
            turn_type = turn.get("type", "")
            text = turn.get("text", "")
            
            if turn_type == "query":
                context_lines.append(f"User originally asked: {text}")
            elif turn_type == "clarification_request":
                context_lines.append(f"System asked: {text}")
            elif turn_type == "clarification_response":
                context_lines.append(f"User clarified: {text}")
            elif turn_type == "confirmation":
                context_lines.append(f"User {text}")
        
        context_lines.append("")  # Empty line for separation
    
    conversation_context = "\n".join(context_lines) if context_lines else None
    
    return classify_intent_safe(query, current_date, conversation_context)

