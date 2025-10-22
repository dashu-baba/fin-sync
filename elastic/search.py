from typing import List, Dict, Any, Tuple
from elastic.client import es
from core.logger import get_logger as log
from core.config import config as cfg
import math

from elastic.embedding import embed_texts

log = log("elastic/search")

def _vector_query(user_query: str, k: int = 12) -> Dict[str, Any]:
    log.info(f"Vector query: user_query={user_query} k={k}")
    embedding = embed_texts([user_query], project_id=cfg.gcp_project_id, location=cfg.gcp_location, model_name=cfg.vertex_model_embed)
    # Use ES text expansion or dense_vector knn. Assuming dense_vector kNN here.
    return {
        "knn": {
            "field": cfg.elastic_vector_field,
            # "query_vector_builder": { "text_embedding": { "model_id": 'text_embedding' , "model_text": user_query } },
            "k": k,
            "num_candidates": k * 4,
            "query_vector": embedding[0]
        }
    }

def _keyword_query(user_query: str, filters: Dict[str, Any], size: int = 20) -> Dict[str, Any]:
    must = [{"multi_match": {"query": user_query, "fields": ["bankName", "accountName", "description", "category", "currency"]}}]
    if date_from := filters.get("date_from"):
        must.append({"range": {"statementDate": {"gte": date_from}}})
    if date_to := filters.get("date_to"):
        must.append({"range": {"statementDate": {"lte": date_to}}})
    if acct := filters.get("accountNo"):
        must.append({"term": {"accountNo": acct}})
    return {
        "size": size,
        "query": {"bool": {"must": must}}
    }

def _rrf(blended_lists: List[List[Dict[str, Any]]], k: int = 20, k_rrf: int = 60) -> List[Dict[str, Any]]:
    scores = {}
    seen = {}
    for lst in blended_lists:
        for rank, hit in enumerate(lst, start=1):
            doc_id = hit["_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank)
            seen[doc_id] = hit
    ranked = sorted(seen.values(), key=lambda h: scores[h["_id"]], reverse=True)
    return ranked[:k]

def vector_search_transactions(query: str, size: int = 12) -> List[Dict[str, Any]]:
    body = {
        "size": size,
        **_vector_query(query, k=size),
        "_source": ["id","accountNo","bankName","accountName","type","amount","balance","description","category","currency","sourceStatementId","sourceFile"]
    }
    res = es().search(index=cfg.elastic_alias_txn_view, body=body)
    return res["hits"]["hits"]

def keyword_search_transactions(query: str, filters: Dict[str, Any], size: int = 20) -> List[Dict[str, Any]]:
    body = _keyword_query(query, filters=filters, size=size)
    body["_source"] = ["id","accountNo","bankName","accountName","type","amount","balance","description","category","currency","sourceStatementId","sourceFile"]

    log.info(f"Keyword search transactions body: {body}")
    res = es().search(index=cfg.elastic_alias_txn_view, body=body)
    return res["hits"]["hits"]

def hybrid_search(query: str, filters: Dict[str, Any], top_k: int = 20) -> Dict[str, Any]:
    log.info(f"Hybrid search: query={query} filters={filters}")

    # Vector on TRANSACTIONS (uses desc_vector)
    try:
        vec_hits = vector_search_transactions(query, size=min(12, top_k))
    except Exception as e:
        log.error(f"Error vector searching transactions: {e}")
        vec_hits = []

    # Keyword on TRANSACTIONS
    try:
        kw_hits = keyword_search_transactions(query, filters=filters, size=min(24, max(10, top_k*2)))
    except Exception as e:
        log.error(f"Error keyword searching transactions: {e}")
        kw_hits = []

    fused = _rrf([vec_hits, kw_hits], k=top_k)
    return {
        "transactions_vector": vec_hits,
        "transactions_keyword": kw_hits,
        "fused": fused
    }

