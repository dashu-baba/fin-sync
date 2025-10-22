from typing import Dict, Any, List
from google.cloud import aiplatform
from core.config import config as cfg
from core.logger import get_logger as log
from elastic import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

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
        )

    t_parts: List[str] = []
    for h in transactions[:20]:
        src = _src(h)
        t_parts.append(
            f"[{_hit_index(h)}#{_hit_id(h)}] "
            f"{src.get('statementDate','')} {src.get('statementType','')} {src.get('statementAmount','')} "
            f"bal={src.get('statementBalance','')} • {_short(src.get('statementDescription',''))} "
            f"| acct={src.get('accountNo','')}"
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

def chat_vertex(question: str, statements, transactions) -> str:
    log.info(f"Chatting with Vertex AI: question={question}")
    from vertexai.generative_models import GenerativeModel
    init_vertex()
    try:
        model = GenerativeModel(cfg.vertex_model_genai)
        user_prompt = build_user_prompt(question, statements, transactions)
        resp = model.generate_content([SYSTEM_PROMPT, user_prompt])
        return (resp.text or "").strip() or "(no response)"
    except Exception as e:
        # Log full context safely
        log.exception(f"Vertex chat failed: {e}")
        return f"Sorry, I couldn’t generate an answer ({type(e).__name__})."
