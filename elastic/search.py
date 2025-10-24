"""
Elasticsearch search functionality with hybrid search support.

Provides search functions for:
- Vector search using embeddings
- Keyword search using BM25
- Hybrid search combining both approaches with RRF
"""
from __future__ import annotations
from typing import List, Dict, Any

from elasticsearch.exceptions import ElasticsearchException

from elastic.client import es
from elastic.embedding import embed_texts
from core.logger import get_logger
from core.config import config as cfg

log = get_logger("elastic/search")

def _vector_query(user_query: str, k: int = 12) -> Dict[str, Any]:
    """
    Build vector search query using embeddings.
    
    Args:
        user_query: Query text to embed and search
        k: Number of top results to return
        
    Returns:
        Dict containing kNN query structure for Elasticsearch
        
    Raises:
        RuntimeError: If embedding generation fails
    """
    log.info(f"Building vector query: user_query='{user_query[:50]}...' k={k}")
    
    try:
        # Generate embedding for query
        embedding = embed_texts(
            [user_query],
            project_id=cfg.gcp_project_id,
            location=cfg.gcp_location,
            model_name=cfg.vertex_model_embed
        )
        
        query = {
            "knn": {
                "field": cfg.elastic_vector_field,
                "k": k,
                "num_candidates": k * 4,
                "query_vector": embedding[0]
            }
        }
        
        log.debug(
            f"Vector query built: field={cfg.elastic_vector_field} "
            f"k={k} num_candidates={k * 4}"
        )
        
        return query
        
    except Exception as e:
        log.error(f"Failed to build vector query: {e}", exc_info=True)
        raise RuntimeError(f"Failed to build vector query: {e}")

def _keyword_query(user_query: str, filters: Dict[str, Any], size: int = 20) -> Dict[str, Any]:
    """
    Build keyword search query with filters.
    
    Uses BM25 relevance scoring across multiple text fields.
    
    Args:
        user_query: Query text for keyword search
        filters: Dictionary of filters (date_from, date_to, accountNo)
        size: Maximum number of results
        
    Returns:
        Dict containing Elasticsearch query structure
    """
    log.debug(f"Building keyword query: user_query='{user_query[:50]}...' filters={filters} size={size}")
    
    # Build must clauses
    must = [
        {
            "multi_match": {
                "query": user_query,
                "fields": [
                    "bankName",
                    "accountName",
                    "description",
                    "category",
                    "currency"
                ],
                "type": "best_fields"
            }
        }
    ]
    
    # Add date range filters
    if date_from := filters.get("date_from"):
        must.append({"range": {"statementDate": {"gte": date_from}}})
        log.debug(f"Added date_from filter: {date_from}")
    
    if date_to := filters.get("date_to"):
        must.append({"range": {"statementDate": {"lte": date_to}}})
        log.debug(f"Added date_to filter: {date_to}")
    
    # Add account filter
    if acct := filters.get("accountNo"):
        must.append({"term": {"accountNo": acct}})
        log.debug(f"Added accountNo filter: {acct}")
    
    return {
        "size": size,
        "query": {"bool": {"must": must}}
    }

def _rrf(blended_lists: List[List[Dict[str, Any]]], k: int = 20, k_rrf: int = 60) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) for combining multiple result lists.
    
    Combines results from multiple search strategies (e.g., vector + keyword)
    using reciprocal rank fusion scoring.
    
    Args:
        blended_lists: List of result lists to combine
        k: Number of top results to return
        k_rrf: RRF constant (default 60, standard value)
        
    Returns:
        List of fused results, sorted by combined score
        
    Reference:
        https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
    """
    log.debug(f"Applying RRF fusion: lists={len(blended_lists)} k={k} k_rrf={k_rrf}")
    
    scores = {}
    seen = {}
    
    # Calculate RRF scores
    for list_idx, lst in enumerate(blended_lists):
        log.debug(f"Processing list {list_idx}: {len(lst)} results")
        
        for rank, hit in enumerate(lst, start=1):
            doc_id = hit["_id"]
            rrf_score = 1.0 / (k_rrf + rank)
            
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score
            seen[doc_id] = hit
    
    # Sort by combined score
    ranked = sorted(
        seen.values(),
        key=lambda h: scores[h["_id"]],
        reverse=True
    )
    
    result = ranked[:k]
    
    log.debug(
        f"RRF fusion complete: input_docs={sum(len(l) for l in blended_lists)} "
        f"unique_docs={len(seen)} output_docs={len(result)}"
    )
    
    return result

def vector_search_transactions(query: str, size: int = 12) -> List[Dict[str, Any]]:
    """
    Search transactions using vector similarity.
    
    Args:
        query: Query text to search for
        size: Number of results to return
        
    Returns:
        List of matching transaction documents
        
    Raises:
        ElasticsearchException: If search fails
    """
    log.info(f"Vector search on transactions: query='{query[:50]}...' size={size}")
    
    try:
        body = {
            "size": size,
            **_vector_query(query, k=size),
            "_source": [
                "id", "accountNo", "bankName", "accountName", "type",
                "amount", "balance", "description", "category", "currency",
                "sourceStatementId", "sourceFile", "@timestamp"
            ]
        }
        
        res = es().search(index=cfg.elastic_alias_txn_view, body=body)
        hits = res["hits"]["hits"]
        
        log.info(f"Vector search completed: found={len(hits)} results")
        return hits
        
    except ElasticsearchException as e:
        log.error(f"Elasticsearch error during vector search: {e}", exc_info=True)
        raise
    except Exception as e:
        log.error(f"Unexpected error during vector search: {e}", exc_info=True)
        raise


def keyword_search_transactions(query: str, filters: Dict[str, Any], size: int = 20) -> List[Dict[str, Any]]:
    """
    Search transactions using keyword matching and filters.
    
    Args:
        query: Query text for keyword search
        filters: Dictionary of filters to apply
        size: Number of results to return
        
    Returns:
        List of matching transaction documents
        
    Raises:
        ElasticsearchException: If search fails
    """
    log.info(
        f"Keyword search on transactions: query='{query[:50]}...' "
        f"filters={filters} size={size}"
    )
    
    try:
        body = _keyword_query(query, filters=filters, size=size)
        body["_source"] = [
            "id", "accountNo", "bankName", "accountName", "type",
            "amount", "balance", "description", "category", "currency",
            "sourceStatementId", "sourceFile", "@timestamp"
        ]
        
        log.debug(f"Keyword search body: {body}")
        
        res = es().search(index=cfg.elastic_alias_txn_view, body=body)
        hits = res["hits"]["hits"]
        
        log.info(f"Keyword search completed: found={len(hits)} results")
        return hits
        
    except ElasticsearchException as e:
        log.error(f"Elasticsearch error during keyword search: {e}", exc_info=True)
        raise
    except Exception as e:
        log.error(f"Unexpected error during keyword search: {e}", exc_info=True)
        raise


def hybrid_search(query: str, filters: Dict[str, Any], top_k: int = 20) -> Dict[str, Any]:
    """
    Hybrid search combining vector and keyword search with RRF.
    
    Performs both vector (semantic) and keyword (BM25) searches,
    then combines results using Reciprocal Rank Fusion.
    
    Args:
        query: Query text to search for
        filters: Dictionary of filters to apply
        top_k: Number of top results to return after fusion
        
    Returns:
        Dict containing:
            - transactions_vector: Vector search results
            - transactions_keyword: Keyword search results
            - fused: RRF-fused results
    """
    log.info(
        f"Hybrid search: query='{query[:50]}...' "
        f"filters={filters} top_k={top_k}"
    )
    
    vec_hits = []
    kw_hits = []
    
    # Vector search on transactions
    try:
        vec_hits = vector_search_transactions(query, size=min(12, top_k))
    except Exception as e:
        log.error(f"Vector search failed in hybrid search: {e}")
        # Continue with empty vector results

    # Keyword search on transactions
    try:
        kw_size = min(24, max(10, top_k * 2))
        kw_hits = keyword_search_transactions(query, filters=filters, size=kw_size)
    except Exception as e:
        log.error(f"Keyword search failed in hybrid search: {e}")
        # Continue with empty keyword results

    # Fuse results
    if vec_hits or kw_hits:
        fused = _rrf([vec_hits, kw_hits], k=top_k)
        log.info(
            f"Hybrid search completed: vector={len(vec_hits)} "
            f"keyword={len(kw_hits)} fused={len(fused)}"
        )
    else:
        fused = []
        log.warning("Hybrid search returned no results from either strategy")
    
    return {
        "transactions_vector": vec_hits,
        "transactions_keyword": kw_hits,
        "fused": fused
    }

