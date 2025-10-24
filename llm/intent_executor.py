"""Orchestrate intent execution by routing to appropriate executors and composers."""
from __future__ import annotations
from typing import Dict, Any
from core.logger import get_logger
from models.intent import IntentResponse
from elastic.executors import execute_aggregate, execute_trend, execute_listing, execute_text_qa, execute_aggregate_filtered_by_text
from llm.vertex_chat import compose_aggregate_answer, compose_text_qa_answer, compose_aggregate_filtered_answer, chat_vertex

log = get_logger("llm/intent_executor")


def execute_intent(query: str, intent_response: IntentResponse) -> Dict[str, Any]:
    """
    Execute intent and generate answer.
    
    Routes to appropriate executor based on intent type:
    - aggregate: execute_aggregate() → compose_aggregate_answer()
    - trend: execute_trend() → compose_trend_answer()
    - listing: execute_listing() → compose_listing_answer()
    - text_qa: hybrid search + chat_vertex()
    - aggregate_filtered_by_text: two-step execution
    - provenance: semantic search with citations
    
    Args:
        query: User's query string
        intent_response: Intent classification response
        
    Returns:
        {
            "intent": str,
            "answer": str,
            "data": dict,  # Raw data (aggs, buckets, hits, etc.)
            "citations": list,  # Optional citations
            "error": str  # Optional error message
        }
    """
    intent = intent_response.classification.intent
    plan = intent_response.classification
    
    log.info(f"Executing intent: {intent}")
    
    try:
        if intent == "aggregate":
            return _execute_aggregate(query, plan)
        
        elif intent == "trend":
            return _execute_trend(query, plan)
        
        elif intent == "listing":
            return _execute_listing(query, plan)
        
        elif intent == "text_qa":
            return _execute_text_qa(query, plan)
        
        elif intent == "aggregate_filtered_by_text":
            return _execute_aggregate_filtered_by_text(query, plan)
        
        elif intent == "provenance":
            return _execute_provenance(query, plan)
        
        else:
            log.warning(f"Unknown intent: {intent}, falling back to text_qa")
            return _execute_text_qa(query, plan)
            
    except Exception as e:
        log.exception(f"Error executing intent {intent}: {e}")
        return {
            "intent": intent,
            "answer": f"Sorry, I encountered an error while processing your request: {str(e)}",
            "data": {},
            "citations": [],
            "error": str(e)
        }


def _execute_aggregate(query: str, plan) -> Dict[str, Any]:
    """Execute aggregate intent."""
    log.info("Executing aggregate intent")
    
    # Step 1: Execute aggregation query
    result = execute_aggregate(plan)
    
    if "error" in result:
        return {
            "intent": "aggregate",
            "answer": f"Sorry, I couldn't retrieve the aggregate data: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    # Step 2: Compose natural language answer
    answer = compose_aggregate_answer(query, result.get("aggs", {}), plan)
    
    return {
        "intent": "aggregate",
        "answer": answer,
        "data": result,
        "citations": []
    }


def _execute_trend(query: str, plan) -> Dict[str, Any]:
    """Execute trend intent."""
    log.info("Executing trend intent")
    
    # Step 1: Execute trend query
    result = execute_trend(plan)
    
    if "error" in result:
        return {
            "intent": "trend",
            "answer": f"Sorry, I couldn't retrieve the trend data: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    # Step 2: Compose answer
    # TODO: Implement compose_trend_answer() for better formatting
    # For now, return simple summary
    buckets = result.get("buckets", [])
    if not buckets:
        answer = "No trend data available for the specified period."
    else:
        answer = f"Trend analysis over {len(buckets)} time periods:\n\n"
        for bucket in buckets[:10]:  # Show first 10
            answer += f"• {bucket['date']}: Income ${bucket['income']:,.2f}, Expense ${bucket['expense']:,.2f}, Net ${bucket['net']:,.2f}\n"
        
        if len(buckets) > 10:
            answer += f"\n... and {len(buckets) - 10} more periods"
    
    return {
        "intent": "trend",
        "answer": answer,
        "data": result,
        "citations": []
    }


def _execute_listing(query: str, plan) -> Dict[str, Any]:
    """Execute listing intent."""
    log.info("Executing listing intent")
    
    # Step 1: Execute listing query
    result = execute_listing(plan, limit=50)
    
    if "error" in result:
        return {
            "intent": "listing",
            "answer": f"Sorry, I couldn't retrieve the transactions: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    # Step 2: Format answer
    hits = result.get("hits", [])
    total = result.get("total", 0)
    
    if not hits:
        answer = "No transactions found matching your criteria."
    else:
        answer = f"Found {total} transactions. Here are the most recent:\n\n"
        for hit in hits[:20]:  # Show first 20
            answer += f"• {hit['date'][:10]}: {hit['type'].upper()} ${hit['amount']:,.2f} - {hit['description'][:50]}\n"
        
        if len(hits) > 20:
            answer += f"\n... and {len(hits) - 20} more transactions in results"
    
    return {
        "intent": "listing",
        "answer": answer,
        "data": result,
        "citations": []
    }


def _execute_text_qa(query: str, plan) -> Dict[str, Any]:
    """Execute text_qa intent (semantic Q&A on statements)."""
    log.info("Executing text_qa intent")
    
    # Step 1: Execute hybrid search on statements index
    result = execute_text_qa(query, plan, size=10)
    
    if "error" in result:
        return {
            "intent": "text_qa",
            "answer": f"Sorry, I couldn't search your statements: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    # Step 2: Compose answer with citations
    chunks = result.get("hits", [])
    provenance = result.get("provenance", [])
    
    answer = compose_text_qa_answer(query, chunks, provenance)
    
    return {
        "intent": "text_qa",
        "answer": answer,
        "data": result,
        "citations": provenance  # Return provenance as citations
    }


def _execute_aggregate_filtered_by_text(query: str, plan) -> Dict[str, Any]:
    """Execute aggregate_filtered_by_text intent (two-step: semantic search then aggregate)."""
    log.info("Executing aggregate_filtered_by_text intent")
    
    # Execute two-step query:
    # Step 1: Semantic search on statements (done internally)
    # Step 2: Aggregate transactions with derived filters
    result = execute_aggregate_filtered_by_text(query, plan, size=10)
    
    if "error" in result:
        return {
            "intent": "aggregate_filtered_by_text",
            "answer": f"Sorry, I couldn't complete the analysis: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    # Compose answer with both aggregations and provenance
    aggs = result.get("aggs", {})
    provenance = result.get("provenance", [])
    derived_filters = result.get("derived_filters", [])
    
    answer = compose_aggregate_filtered_answer(
        query, 
        aggs, 
        provenance,
        derived_filters,
        plan
    )
    
    return {
        "intent": "aggregate_filtered_by_text",
        "answer": answer,
        "data": result,
        "citations": provenance  # Return provenance as citations
    }


def _execute_provenance(query: str, plan) -> Dict[str, Any]:
    """Execute provenance intent (show source evidence)."""
    log.info("Executing provenance intent")
    
    # Reuse text_qa to find relevant statements and extract provenance
    # This intent focuses on showing the sources/evidence rather than generating an answer
    result = execute_text_qa(query, plan, size=10)
    
    if "error" in result:
        return {
            "intent": "provenance",
            "answer": f"Sorry, I couldn't find source evidence: {result['error']}",
            "data": result,
            "citations": [],
            "error": result["error"]
        }
    
    chunks = result.get("hits", [])
    provenance = result.get("provenance", [])
    
    if not provenance:
        return {
            "intent": "provenance",
            "answer": "I couldn't find any relevant statements or sources for that query.",
            "data": result,
            "citations": []
        }
    
    # Format provenance-focused answer
    answer_parts = [f"I found {len(provenance)} relevant source(s) in your statements:\n"]
    
    for i, prov in enumerate(provenance, start=1):
        source_info = prov.get("source", "")
        page = prov.get("page", 1)
        score = prov.get("score", 0.0)
        
        # Get corresponding chunk for context
        chunk_text = ""
        if i <= len(chunks):
            chunk_text = chunks[i-1].get("text", "")[:200]  # First 200 chars
        
        answer_parts.append(
            f"\n**[{i}] {source_info}**\n"
            f"  - Page: {page}\n"
            f"  - Relevance Score: {score:.3f}\n"
            f"  - Preview: {chunk_text}...\n"
        )
    
    answer = "".join(answer_parts)
    
    return {
        "intent": "provenance",
        "answer": answer,
        "data": result,
        "citations": provenance
    }

