from typing import Dict, Any, List
from google.cloud import aiplatform
from core.config import config as cfg
from core.logger import get_logger as log
from elastic import SYSTEM_PROMPT

log = log("llm/vertex_chat")

def init_vertex():
    log.info(f"Initializing Vertex AI: {cfg.gcp_project_id}@{cfg.gcp_location}")
    aiplatform.init(project=cfg.gcp_project_id, location=cfg.gcp_location)

def _short(s: str, n: int = 140) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + "…"

def _hit_id(hit: Dict[str, Any]) -> str:
    # Always present on ES hits
    return hit.get("_id") or ""

def _hit_index(hit: Dict[str, Any]) -> str:
    # ES uses _index, not index
    return hit.get("_index") or hit.get("index") or ""

def _src(hit: Dict[str, Any]) -> Dict[str, Any]:
    return hit.get("_source") or {}

def format_docs(statements: List[Dict[str, Any]] | None,
                transactions: List[Dict[str, Any]] | None) -> str:
    statements = statements or []
    transactions = transactions or []

    s_parts: List[str] = []
    for h in statements[:8]:
        src = _src(h)
        s_parts.append(
            f"[{_hit_index(h)}#{_hit_id(h)}] "
            f"{src.get('accountNo','')} {src.get('bankName','')} "
            f"{src.get('statementFrom','')}→{src.get('statementTo','')} | {_short(src.get('summary',''))}"
            f"| {src.get('description','')}"
            f"| {src.get('category','')}"
            f"| {src.get('currency','')}"
            f"| {src.get('sourceStatementId','')}"
            f"| {src.get('sourceFile','')}"
            f"| {src.get('timestamp','')}"
            f"| {src.get('@timestamp','')}"
            f"| {src.get('amount','')}"
            f"| {src.get('balance','')}"
            f"| {src.get('type','')}"
        )

    t_parts: List[str] = []
    for h in transactions[:20]:
        src = _src(h)
        t_parts.append(
            f"[{_hit_index(h)}#{_hit_id(h)}] "
            f"{src.get('statementDate','')} {src.get('statementType','')} {src.get('statementAmount','')} "
            f"bal={src.get('statementBalance','')} • {_short(src.get('statementDescription',''))} "
            f"| acct={src.get('accountNo','')}"
            f"| {src.get('description','')}"
            f"| {src.get('category','')}"
            f"| {src.get('currency','')}"
            f"| {src.get('sourceStatementId','')}"
            f"| {src.get('sourceFile','')}"
            f"| {src.get('timestamp','')}"
            f"| {src.get('@timestamp','')}"
            f"| {src.get('amount','')}"
            f"| {src.get('balance','')}"
            f"| {src.get('type','')}"
            f"| {src.get('id','')}"
        )

    doc = "Statements:\n" + ("\n".join(s_parts) if s_parts else "∅") + \
          "\n\nTransactions:\n" + ("\n".join(t_parts) if t_parts else "∅")
    return doc

def build_user_prompt(question: str, statements, transactions) -> str:
    return (
        f"User question:\n{question}\n\n"
        "Use only the following search results:\n\n"
        f"{format_docs(statements, transactions)}\n\n"
        "If you compute totals, mention the date range/account used. "
        "End with bullets like: • [index#_id] short snippet."
    )

def compose_aggregate_answer(query: str, aggs: Dict[str, Any], plan: Any) -> str:
    """
    Generate natural language answer from aggregate results.
    
    Args:
        query: Original user query
        aggs: Aggregation results from Elasticsearch
        plan: IntentClassification plan with filters
        
    Returns:
        Natural language answer
    """
    log.info("Composing aggregate answer with Vertex AI")
    from vertexai.generative_models import GenerativeModel
    init_vertex()
    
    try:
        # Build context from aggregation results
        agg_context = []
        
        if "sum_income" in aggs:
            agg_context.append(f"Total Income: ${aggs['sum_income']:,.2f}")
        
        if "sum_expense" in aggs:
            agg_context.append(f"Total Expenses: ${aggs['sum_expense']:,.2f}")
        
        if "net" in aggs:
            net = aggs['net']
            net_label = "Net Income" if net >= 0 else "Net Loss"
            agg_context.append(f"{net_label}: ${abs(net):,.2f}")
        
        if "count" in aggs:
            agg_context.append(f"Total Transactions: {aggs['count']}")
        
        if "top_merchants" in aggs and aggs["top_merchants"]:
            merchants_list = []
            for m in aggs["top_merchants"][:5]:
                merchants_list.append(f"  - {m['merchant']}: ${m['total_amount']:,.2f} ({m['count']} transactions)")
            if merchants_list:
                agg_context.append("Top Merchants:\n" + "\n".join(merchants_list))
        
        if "top_categories" in aggs and aggs["top_categories"]:
            categories_list = []
            for c in aggs["top_categories"][:5]:
                categories_list.append(f"  - {c['category']}: ${c['total_amount']:,.2f} ({c['count']} transactions)")
            if categories_list:
                agg_context.append("Top Categories:\n" + "\n".join(categories_list))
        
        # Build filters context
        filters_context = []
        if hasattr(plan, 'filters'):
            if plan.filters.dateFrom:
                filters_context.append(f"From: {plan.filters.dateFrom}")
            if plan.filters.dateTo:
                filters_context.append(f"To: {plan.filters.dateTo}")
            if plan.filters.accountNo:
                filters_context.append(f"Account: {plan.filters.accountNo}")
            if plan.filters.counterparty:
                filters_context.append(f"Counterparty: {plan.filters.counterparty}")
            if plan.filters.minAmount is not None:
                filters_context.append(f"Min Amount: ${plan.filters.minAmount:,.2f}")
            if plan.filters.maxAmount is not None:
                filters_context.append(f"Max Amount: ${plan.filters.maxAmount:,.2f}")
        
        # Build prompt
        system_prompt = """You are a financial assistant helping users understand their transaction data.
Provide clear, concise answers based on the aggregated financial data provided.
Format monetary amounts nicely and highlight key insights."""
        
        user_prompt = f"""User question: {query}

Financial Summary:
{chr(10).join(agg_context)}

Filters Applied:
{chr(10).join(filters_context) if filters_context else "None"}

Please provide a clear, natural language answer to the user's question based on this data.
Keep it concise but informative. Highlight any notable patterns or insights."""
        
        log.debug(f"Aggregate answer prompt: {user_prompt}")
        
        model = GenerativeModel(cfg.vertex_model_genai)
        resp = model.generate_content([system_prompt, user_prompt])
        answer = (resp.text or "").strip() or "(no response)"
        
        log.info("Aggregate answer generated successfully")
        return answer
        
    except Exception as e:
        log.exception(f"Error composing aggregate answer: {e}")
        # Fallback to simple text summary
        summary_parts = []
        if "sum_income" in aggs:
            summary_parts.append(f"Total Income: ${aggs['sum_income']:,.2f}")
        if "sum_expense" in aggs:
            summary_parts.append(f"Total Expenses: ${aggs['sum_expense']:,.2f}")
        if "net" in aggs:
            summary_parts.append(f"Net: ${aggs['net']:,.2f}")
        if "count" in aggs:
            summary_parts.append(f"Transactions: {aggs['count']}")
        
        return "Here's your financial summary:\n" + "\n".join(summary_parts) if summary_parts else "No data available for the specified criteria."


def compose_text_qa_answer(query: str, chunks: List[Dict[str, Any]], provenance: List[Dict[str, Any]]) -> str:
    """
    Generate natural language answer from text QA search results with citations.
    
    Args:
        query: Original user query
        chunks: Retrieved statement chunks
        provenance: Provenance information with citations
        
    Returns:
        Natural language answer with citations
    """
    log.info("Composing text QA answer with citations")
    from vertexai.generative_models import GenerativeModel
    init_vertex()
    
    try:
        if not chunks:
            return "I couldn't find any relevant information in your bank statements to answer that question."
        
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks[:5], start=1):  # Limit to top 5 chunks
            text = chunk.get("text", "")[:400]  # Truncate long chunks
            source_info = f"{chunk.get('bankName', '')} - Account {chunk.get('accountNo', '')} ({chunk.get('statementFrom', '')} to {chunk.get('statementTo', '')})"
            context_parts.append(f"[{i}] {source_info}\n{text}")
        
        context_text = "\n\n".join(context_parts)
        
        # Build citations list
        citations_text = []
        for i, prov in enumerate(provenance[:5], start=1):
            citations_text.append(
                f"[{i}] {prov.get('source', '')} (Page {prov.get('page', 1)}, Score: {prov.get('score', 0.0):.3f})"
            )
        
        # Build prompt
        system_prompt = """You are a financial assistant helping users understand their bank statement data.
Provide clear, accurate answers based ONLY on the provided statement excerpts.
Always cite your sources using the [N] format provided in the context.
If the information is not in the provided statements, say so clearly."""
        
        user_prompt = f"""User question: {query}

Relevant statement excerpts:
{context_text}

Please answer the user's question based on the above statements. 
Include citations [1], [2], etc. in your answer to reference specific statements.
Keep the answer clear and concise."""
        
        log.debug(f"Text QA prompt: {user_prompt[:500]}...")
        
        model = GenerativeModel(cfg.vertex_model_genai)
        resp = model.generate_content([system_prompt, user_prompt])
        answer = (resp.text or "").strip()
        
        if not answer:
            answer = "I found relevant statements but couldn't generate a clear answer."
        
        # Append citations section
        if citations_text:
            answer += "\n\n**Sources:**\n" + "\n".join(citations_text)
        
        log.info("Text QA answer generated successfully with citations")
        return answer
        
    except Exception as e:
        log.exception(f"Error composing text QA answer: {e}")
        
        # Fallback: simple summary
        if not chunks:
            return "No relevant statements found."
        
        fallback = f"Found {len(chunks)} relevant statement(s):\n\n"
        for i, chunk in enumerate(chunks[:3], start=1):
            text = chunk.get("text", "")[:200]
            fallback += f"{i}. {chunk.get('bankName', '')} ({chunk.get('statementFrom', '')}): {text}...\n\n"
        
        if provenance:
            fallback += "\nSources:\n"
            for i, prov in enumerate(provenance[:3], start=1):
                fallback += f"[{i}] {prov.get('source', '')}\n"
        
        return fallback


def compose_aggregate_filtered_answer(
    query: str, 
    aggs: Dict[str, Any], 
    provenance: List[Dict[str, Any]],
    derived_filters: List[str],
    plan: Any
) -> str:
    """
    Generate natural language answer from aggregate_filtered_by_text results with citations.
    
    This combines aggregate results with statement provenance to show:
    1. The aggregated financial data
    2. The statement context that informed the filters
    3. Citations to source statements
    
    Args:
        query: Original user query
        aggs: Aggregation results from transactions
        provenance: Provenance from statement search
        derived_filters: List of filter terms derived from statements
        plan: IntentClassification plan with filters
        
    Returns:
        Natural language answer with citations
    """
    log.info("Composing aggregate filtered by text answer with citations")
    from vertexai.generative_models import GenerativeModel
    init_vertex()
    
    try:
        # Build context from aggregation results
        agg_context = []
        
        if "sum_income" in aggs:
            agg_context.append(f"Total Income: ${aggs['sum_income']:,.2f}")
        
        if "sum_expense" in aggs:
            agg_context.append(f"Total Expenses: ${aggs['sum_expense']:,.2f}")
        
        if "net" in aggs:
            net = aggs['net']
            net_label = "Net Income" if net >= 0 else "Net Loss"
            agg_context.append(f"{net_label}: ${abs(net):,.2f}")
        
        if "count" in aggs:
            agg_context.append(f"Total Transactions: {aggs['count']}")
        
        if "top_merchants" in aggs and aggs["top_merchants"]:
            merchants_list = []
            for m in aggs["top_merchants"][:5]:
                merchants_list.append(f"  - {m['merchant']}: ${m['total_amount']:,.2f} ({m['count']} transactions)")
            if merchants_list:
                agg_context.append("Top Merchants:\n" + "\n".join(merchants_list))
        
        if "top_categories" in aggs and aggs["top_categories"]:
            categories_list = []
            for c in aggs["top_categories"][:5]:
                categories_list.append(f"  - {c['category']}: ${c['total_amount']:,.2f} ({c['count']} transactions)")
            if categories_list:
                agg_context.append("Top Categories:\n" + "\n".join(categories_list))
        
        # Build filters context
        filters_context = []
        if hasattr(plan, 'filters'):
            if plan.filters.dateFrom:
                filters_context.append(f"From: {plan.filters.dateFrom}")
            if plan.filters.dateTo:
                filters_context.append(f"To: {plan.filters.dateTo}")
            if plan.filters.accountNo:
                filters_context.append(f"Account: {plan.filters.accountNo}")
        
        # Build derived filters context
        derived_context = []
        if derived_filters:
            derived_context.append("Filters derived from your statements:")
            for i, term in enumerate(derived_filters[:3], start=1):
                term_short = term[:80] + "..." if len(term) > 80 else term
                derived_context.append(f"  {i}. Matching: \"{term_short}\"")
        
        # Build citations
        citations_text = []
        if provenance:
            for i, prov in enumerate(provenance[:5], start=1):
                citations_text.append(
                    f"[{i}] {prov.get('source', '')} (Page {prov.get('page', 1)})"
                )
        
        # Build prompt
        system_prompt = """You are a financial assistant helping users understand their transaction data.
You have aggregated transaction data based on filters derived from the user's bank statements.
Provide clear, concise answers that connect the statement context to the aggregated results.
Include citations to show which statements informed the analysis."""
        
        user_prompt = f"""User question: {query}

Financial Summary (aggregated transactions):
{chr(10).join(agg_context)}

{chr(10).join(derived_context) if derived_context else ''}

Base Filters:
{chr(10).join(filters_context) if filters_context else "None"}

Statement Context (what we searched):
Found {len(provenance)} relevant statement excerpts that helped identify transactions.

Please provide a clear answer that:
1. Summarizes the aggregated transaction data
2. Explains that the analysis was based on information from the user's statements
3. Includes citations [1], [2], etc. to reference which statements informed the analysis
Keep it concise but informative."""
        
        log.debug(f"Aggregate filtered answer prompt: {user_prompt[:500]}...")
        
        model = GenerativeModel(cfg.vertex_model_genai)
        resp = model.generate_content([system_prompt, user_prompt])
        answer = (resp.text or "").strip() or "(no response)"
        
        # Append citations section
        if citations_text:
            answer += "\n\n**Statement Sources:**\n" + "\n".join(citations_text)
            answer += "\n\n*Note: Transaction amounts were aggregated based on patterns found in these statements.*"
        
        log.info("Aggregate filtered answer generated successfully")
        return answer
        
    except Exception as e:
        log.exception(f"Error composing aggregate filtered answer: {e}")
        
        # Fallback to simple summary
        summary_parts = []
        if "sum_income" in aggs:
            summary_parts.append(f"Total Income: ${aggs['sum_income']:,.2f}")
        if "sum_expense" in aggs:
            summary_parts.append(f"Total Expenses: ${aggs['sum_expense']:,.2f}")
        if "net" in aggs:
            summary_parts.append(f"Net: ${aggs['net']:,.2f}")
        if "count" in aggs:
            summary_parts.append(f"Transactions: {aggs['count']}")
        
        fallback = "Based on information from your statements:\n" + "\n".join(summary_parts)
        
        if provenance:
            fallback += "\n\nSources:\n"
            for i, prov in enumerate(provenance[:3], start=1):
                fallback += f"[{i}] {prov.get('source', '')}\n"
        
        return fallback if summary_parts else "No data available matching the statement context."


def chat_vertex(question: str, statements, transactions) -> str:
    log.info(f"Chatting with Vertex AI: question={question} statements={statements} transactions={transactions}")
    from vertexai.generative_models import GenerativeModel
    init_vertex()
    try:
        model = GenerativeModel(cfg.vertex_model_genai)
        user_prompt = build_user_prompt(question, statements, transactions)
        log.info(f"User prompt: {user_prompt}")
        resp = model.generate_content([SYSTEM_PROMPT, user_prompt])
        return (resp.text or "").strip() or "(no response)"
    except Exception as e:
        # Log full context safely
        log.exception(f"Vertex chat failed: {e}")
        return f"Sorry, I couldn't generate an answer ({type(e).__name__})."
