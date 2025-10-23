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
