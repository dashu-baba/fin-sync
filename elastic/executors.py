"""Execute Elasticsearch queries and transform responses for different intents."""
from __future__ import annotations
from typing import Dict, Any, List
from core.logger import get_logger
from core.config import config
from models.intent import IntentClassification, IntentResponse
from elastic.client import es
from elastic.query_builders import q_aggregate, q_trend, q_listing, q_text_qa, q_hybrid
from elastic.embedding import embed_texts

log = get_logger("elastic/executors")


def execute_aggregate(plan: IntentClassification) -> Dict[str, Any]:
    """
    Execute aggregate query and return structured results.
    
    Args:
        plan: IntentClassification with filters and metrics
        
    Returns:
        {
            "intent": "aggregate",
            "aggs": {
                "sum_income": float,
                "sum_expense": float,
                "net": float,
                "count": int,
                "top_merchants": [...],
                "top_categories": [...]
            },
            "filters_applied": {...}
        }
    """
    log.info("Executing aggregate query")
    
    try:
        # Build query
        query = q_aggregate(plan)
        
        # Execute on transactions index
        client = es()
        response = client.search(
            index=config.elastic_index_transactions,
            body=query
        )
        
        log.debug(f"Aggregate query response: {response}")
        
        # Parse aggregations
        aggs = response.get("aggregations", {})
        
        result = {
            "intent": "aggregate",
            "aggs": {},
            "filters_applied": {
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo,
                "accountNo": plan.filters.accountNo,
                "counterparty": plan.filters.counterparty,
                "minAmount": plan.filters.minAmount,
                "maxAmount": plan.filters.maxAmount
            },
            "total_hits": response.get("hits", {}).get("total", {}).get("value", 0)
        }
        
        # Extract sum_income
        if "sum_income" in aggs:
            result["aggs"]["sum_income"] = aggs["sum_income"].get("total", {}).get("value", 0.0) or 0.0
        
        # Extract sum_expense
        if "sum_expense" in aggs:
            result["aggs"]["sum_expense"] = aggs["sum_expense"].get("total", {}).get("value", 0.0) or 0.0
        
        # Extract net
        if "net" in aggs:
            result["aggs"]["net"] = aggs["net"].get("value", 0.0) or 0.0
        
        # Extract count
        if "transaction_count" in aggs:
            result["aggs"]["count"] = aggs["transaction_count"].get("value", 0) or 0
        
        # Extract top merchants
        if "top_merchants" in aggs:
            merchants = []
            for bucket in aggs["top_merchants"].get("buckets", []):
                merchants.append({
                    "merchant": bucket.get("key", ""),
                    "count": bucket.get("doc_count", 0),
                    "total_amount": bucket.get("total_amount", {}).get("value", 0.0) or 0.0
                })
            result["aggs"]["top_merchants"] = merchants
        
        # Extract top categories
        if "top_categories" in aggs:
            categories = []
            for bucket in aggs["top_categories"].get("buckets", []):
                categories.append({
                    "category": bucket.get("key", ""),
                    "count": bucket.get("doc_count", 0),
                    "total_amount": bucket.get("total_amount", {}).get("value", 0.0) or 0.0
                })
            result["aggs"]["top_categories"] = categories
        
        # Extract currency (most common)
        currency = "USD"  # Default fallback
        if "currency_terms" in aggs:
            currency_buckets = aggs["currency_terms"].get("buckets", [])
            if currency_buckets:
                currency = currency_buckets[0].get("key", "USD")
            else:
                # No results with current filters - fetch currency from ANY transaction in the account
                try:
                    fallback_query = {"size": 1, "query": {"match_all": {}}, "_source": ["currency"]}
                    if plan.filters.accountNo:
                        fallback_query["query"] = {"term": {"accountNo": plan.filters.accountNo}}
                    
                    fallback_response = client.search(index=config.elastic_index_transactions, body=fallback_query)
                    fallback_hits = fallback_response.get("hits", {}).get("hits", [])
                    if fallback_hits:
                        currency = fallback_hits[0].get("_source", {}).get("currency", "USD")
                        log.debug(f"Retrieved currency from fallback query: {currency}")
                except Exception as e:
                    log.warning(f"Failed to retrieve currency from fallback query: {e}")
        
        result["currency"] = currency
        log.info(f"Aggregate execution complete: {result['aggs']}, currency: {currency}")
        return result
        
    except Exception as e:
        log.exception(f"Error executing aggregate query: {e}")
        return {
            "intent": "aggregate",
            "error": str(e),
            "aggs": {}
        }


def execute_trend(plan: IntentClassification) -> Dict[str, Any]:
    """
    Execute trend query and return time-series data.
    
    Args:
        plan: IntentClassification with filters and granularity
        
    Returns:
        {
            "intent": "trend",
            "buckets": [
                {
                    "date": "2024-01-01",
                    "income": float,
                    "expense": float,
                    "net": float,
                    "count": int
                },
                ...
            ],
            "filters_applied": {...}
        }
    """
    log.info(f"Executing trend query with granularity: {plan.granularity}")
    
    try:
        # Build query
        query = q_trend(plan)
        
        # Execute
        client = es()
        response = client.search(
            index=config.elastic_index_transactions,
            body=query
        )
        
        log.debug(f"Trend query response: {response}")
        
        # Parse aggregations
        aggs = response.get("aggregations", {})
        trend_buckets = aggs.get("trend", {}).get("buckets", [])
        
        buckets = []
        for bucket in trend_buckets:
            income = bucket.get("income", {}).get("amount", {}).get("value", 0.0) or 0.0
            expense = bucket.get("expense", {}).get("amount", {}).get("value", 0.0) or 0.0
            # Calculate net client-side (income - expense)
            net = income - expense
            
            buckets.append({
                "date": bucket.get("key_as_string", ""),
                "timestamp": bucket.get("key", 0),
                "income": income,
                "expense": expense,
                "net": net,
                "count": bucket.get("doc_count", 0)
            })
        
        # Extract currency (most common)
        currency = "USD"  # Default fallback
        if "currency_terms" in aggs:
            currency_buckets = aggs["currency_terms"].get("buckets", [])
            if currency_buckets:
                currency = currency_buckets[0].get("key", "USD")
            else:
                # No results with current filters - fetch currency from ANY transaction in the account
                try:
                    fallback_query = {"size": 1, "query": {"match_all": {}}, "_source": ["currency"]}
                    if plan.filters.accountNo:
                        fallback_query["query"] = {"term": {"accountNo": plan.filters.accountNo}}
                    
                    fallback_response = client.search(index=config.elastic_index_transactions, body=fallback_query)
                    fallback_hits = fallback_response.get("hits", {}).get("hits", [])
                    if fallback_hits:
                        currency = fallback_hits[0].get("_source", {}).get("currency", "USD")
                        log.debug(f"Retrieved currency from fallback query: {currency}")
                except Exception as e:
                    log.warning(f"Failed to retrieve currency from fallback query: {e}")
        
        result = {
            "intent": "trend",
            "granularity": plan.granularity,
            "buckets": buckets,
            "currency": currency,
            "filters_applied": {
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo,
                "accountNo": plan.filters.accountNo,
                "counterparty": plan.filters.counterparty,
                "minAmount": plan.filters.minAmount,
                "maxAmount": plan.filters.maxAmount
            }
        }
        
        log.info(f"Trend execution complete: {len(buckets)} buckets, currency: {currency}")
        return result
        
    except Exception as e:
        log.exception(f"Error executing trend query: {e}")
        return {
            "intent": "trend",
            "error": str(e),
            "buckets": []
        }


def execute_listing(plan: IntentClassification, limit: int = 50) -> Dict[str, Any]:
    """
    Execute listing query and return transaction rows.
    
    Args:
        plan: IntentClassification with filters
        limit: Number of results to return
        
    Returns:
        {
            "intent": "listing",
            "hits": [
                {
                    "date": "2024-01-15",
                    "amount": 150.50,
                    "type": "debit",
                    "description": "...",
                    "merchant": "...",
                    "accountNo": "...",
                    "balance": 5000.00
                },
                ...
            ],
            "filters_applied": {...},
            "total": int
        }
    """
    log.info(f"Executing listing query with limit={limit}")
    
    try:
        # Build query
        query = q_listing(plan, limit=limit)
        
        # Execute
        client = es()
        response = client.search(
            index=config.elastic_index_transactions,
            body=query
        )
        
        log.debug(f"Listing query response: {response}")
        
        # Parse hits
        hits = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            hits.append({
                "date": source.get("@timestamp", ""),
                "amount": source.get("amount", 0.0),
                "type": source.get("type", ""),
                "description": source.get("description", ""),
                "category": source.get("category", ""),
                "accountNo": source.get("accountNo", ""),
                "balance": source.get("balance", 0.0),
                "bankName": source.get("bankName", ""),
                "currency": source.get("currency", "USD")
            })
        
        result = {
            "intent": "listing",
            "hits": hits,
            "total": response.get("hits", {}).get("total", {}).get("value", 0),
            "filters_applied": {
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo,
                "accountNo": plan.filters.accountNo,
                "counterparty": plan.filters.counterparty,
                "minAmount": plan.filters.minAmount,
                "maxAmount": plan.filters.maxAmount
            }
        }
        
        log.info(f"Listing execution complete: {len(hits)} transactions")
        return result
        
    except Exception as e:
        log.exception(f"Error executing listing query: {e}")
        return {
            "intent": "listing",
            "error": str(e),
            "hits": []
        }


def execute_text_qa(user_query: str, plan: IntentClassification, size: int = 10) -> Dict[str, Any]:
    """
    Execute text_qa query with hybrid search on statements index.
    
    Performs:
    1. Keyword search (BM25) on statement text fields
    2. Vector search (kNN) on statement embeddings
    3. RRF fusion of results
    4. Extract provenance (statementId, page, score)
    
    Args:
        user_query: User's question
        plan: IntentClassification with filters
        size: Number of results to return
        
    Returns:
        {
            "intent": "text_qa",
            "hits": [chunks...],
            "provenance": [
                {"statementId": str, "page": int, "score": float, "source": str}
            ],
            "filters_applied": {...}
        }
    """
    log.info(f"Executing text_qa query: {user_query}")
    
    try:
        # Build queries
        queries = q_text_qa(user_query, filters=plan.filters, size=size)
        
        client = es()
        index = config.elastic_index_statements
        
        # Execute keyword search (BM25)
        log.info("Executing keyword search on statements")
        keyword_response = client.search(
            index=index,
            body=queries["keyword_query"]
        )
        keyword_hits = keyword_response.get("hits", {}).get("hits", [])
        log.info(f"Keyword search returned {len(keyword_hits)} hits")
        
        # Execute vector search (kNN)
        log.info("Generating embedding for vector search")
        try:
            embeddings = embed_texts(
                [user_query],
                project_id=config.gcp_project_id,
                location=config.gcp_location,
                model_name=config.vertex_model_embed
            )
            query_embedding = embeddings[0]
            
            # Build kNN query
            vector_query = {
                "size": size,
                "knn": {
                    "field": "summary_vector",  # or content_vector depending on index
                    "query_vector": query_embedding,
                    "k": size,
                    "num_candidates": size * 4
                },
                "_source": queries["vector_query_template"]["_source"]
            }
            
            # Add filters if present
            if queries["vector_query_template"]["query"]["bool"].get("filter"):
                vector_query["filter"] = queries["vector_query_template"]["query"]["bool"]["filter"]
            
            log.info("Executing vector search on statements")
            vector_response = client.search(
                index=index,
                body=vector_query
            )
            vector_hits = vector_response.get("hits", {}).get("hits", [])
            log.info(f"Vector search returned {len(vector_hits)} hits")
            
        except Exception as e:
            log.warning(f"Vector search failed: {e}, using keyword results only")
            vector_hits = []
        
        # RRF Fusion
        log.info("Fusing results with RRF")
        fused_hits = _rrf_fusion([keyword_hits, vector_hits], k=size)
        
        # Extract chunks and provenance
        chunks = []
        provenance = []
        
        for hit in fused_hits:
            source = hit.get("_source", {})
            doc_id = hit.get("_id", "")
            score = hit.get("_score", 0.0)
            
            # Extract chunk text
            chunk_text = source.get("summary_text", "") or source.get("rawText", "")
            if chunk_text:
                chunk_text = chunk_text[:500]  # Limit chunk size
            
            chunks.append({
                "id": doc_id,
                "text": chunk_text,
                "accountNo": source.get("accountNo", ""),
                "bankName": source.get("bankName", ""),
                "statementFrom": source.get("statementFrom", ""),
                "statementTo": source.get("statementTo", ""),
                "score": score
            })
            
            # Extract provenance
            provenance.append({
                "statementId": doc_id,
                "page": source.get("meta", {}).get("page", 1) if isinstance(source.get("meta"), dict) else 1,
                "score": score,
                "source": f"{source.get('bankName', '')} - {source.get('accountNo', '')} ({source.get('statementFrom', '')} to {source.get('statementTo', '')})"
            })
        
        result = {
            "intent": "text_qa",
            "hits": chunks,
            "provenance": provenance,
            "filters_applied": {
                "accountNo": plan.filters.accountNo,
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo
            },
            "total_hits": len(fused_hits)
        }
        
        log.info(f"Text QA execution complete: {len(chunks)} chunks with provenance")
        return result
        
    except Exception as e:
        log.exception(f"Error executing text_qa query: {e}")
        return {
            "intent": "text_qa",
            "error": str(e),
            "hits": [],
            "provenance": []
        }


def _rrf_fusion(hit_lists: List[List[Dict[str, Any]]], k: int = 10, k_rrf: int = 60) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) to combine multiple ranked lists.
    
    Args:
        hit_lists: List of hit lists from different searches
        k: Number of results to return
        k_rrf: RRF parameter (default 60)
        
    Returns:
        Fused and re-ranked list of hits
    """
    scores: Dict[str, float] = {}
    docs: Dict[str, Dict[str, Any]] = {}
    
    for hit_list in hit_lists:
        for rank, hit in enumerate(hit_list, start=1):
            doc_id = hit.get("_id", "")
            if not doc_id:
                continue
            
            # RRF score: 1 / (k + rank)
            rrf_score = 1.0 / (k_rrf + rank)
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score
            
            # Keep the hit document
            if doc_id not in docs:
                docs[doc_id] = hit
    
    # Sort by RRF score
    sorted_docs = sorted(docs.values(), key=lambda h: scores.get(h.get("_id", ""), 0.0), reverse=True)
    
    # Update scores with RRF scores
    for doc in sorted_docs:
        doc["_score"] = scores.get(doc.get("_id", ""), 0.0)
    
    return sorted_docs[:k]


def execute_aggregate_filtered_by_text(
    user_query: str, 
    plan: IntentClassification,
    size: int = 10
) -> Dict[str, Any]:
    """
    Execute aggregate_filtered_by_text query - two-step execution.
    
    Step 1: Semantic search on statements to find relevant context
    Step 2: Use derived filters from statements to aggregate transactions
    
    Args:
        user_query: User's question
        plan: IntentClassification with filters and metrics
        size: Number of statement hits to use for filter derivation
        
    Returns:
        {
            "intent": "aggregate_filtered_by_text",
            "aggs": {aggregation results},
            "provenance": [{statement sources}],
            "filters_applied": {...},
            "derived_filters": [list of terms used]
        }
    """
    log.info(f"Executing aggregate_filtered_by_text query: {user_query}")
    
    try:
        client = es()
        
        # Step 1: Execute text_qa on statements to find relevant context
        log.info("Step 1: Searching statements for relevant context")
        statement_result = execute_text_qa(user_query, plan, size=size)
        
        if "error" in statement_result:
            return {
                "intent": "aggregate_filtered_by_text",
                "error": f"Failed to search statements: {statement_result['error']}",
                "aggs": {},
                "provenance": []
            }
        
        statement_hits = statement_result.get("hits", [])
        provenance = statement_result.get("provenance", [])
        
        if not statement_hits:
            log.warning("No statement hits found, falling back to regular aggregate")
            # Fallback to regular aggregate without derived filters
            return execute_aggregate(plan)
        
        log.info(f"Found {len(statement_hits)} relevant statements")
        
        # Step 2: Build aggregate query with derived filters from statements
        log.info("Step 2: Building aggregate query with derived filters")
        
        # Convert statement hits to format expected by q_hybrid
        # (they're already in the right format with _source, _id, etc.)
        raw_hits = []
        for chunk in statement_hits:
            # Reconstruct ES hit format
            hit = {
                "_id": chunk.get("id", ""),
                "_source": {
                    "summary_text": chunk.get("text", ""),
                    "accountNo": chunk.get("accountNo", ""),
                    "bankName": chunk.get("bankName", ""),
                    "statementFrom": chunk.get("statementFrom", ""),
                    "statementTo": chunk.get("statementTo", "")
                }
            }
            raw_hits.append(hit)
        
        # Build query with derived filters
        hybrid_query = q_hybrid(user_query, plan, raw_hits)
        
        # Extract derived terms for reporting
        derived_filters = []
        query_bool = hybrid_query.get("query", {}).get("bool", {})
        for must_clause in query_bool.get("must", []):
            if "bool" in must_clause and "should" in must_clause["bool"]:
                for should_clause in must_clause["bool"]["should"]:
                    if "match_phrase" in should_clause:
                        desc_query = should_clause["match_phrase"].get("description", {})
                        if isinstance(desc_query, dict):
                            derived_filters.append(desc_query.get("query", ""))
                        else:
                            derived_filters.append(desc_query)
        
        log.info(f"Derived {len(derived_filters)} filter terms from statements")
        
        # Step 3: Execute aggregate query on transactions
        log.info("Step 3: Executing aggregate query on transactions")
        response = client.search(
            index=config.elastic_index_transactions,
            body=hybrid_query
        )
        
        log.debug(f"Aggregate response: {response}")
        
        # Parse aggregations (same logic as execute_aggregate)
        aggs = response.get("aggregations", {})
        
        result = {
            "intent": "aggregate_filtered_by_text",
            "aggs": {},
            "provenance": provenance,  # From statement search
            "filters_applied": {
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo,
                "accountNo": plan.filters.accountNo,
                "counterparty": plan.filters.counterparty,
                "minAmount": plan.filters.minAmount,
                "maxAmount": plan.filters.maxAmount
            },
            "derived_filters": derived_filters,
            "total_hits": response.get("hits", {}).get("total", {}).get("value", 0),
            "statement_context": len(statement_hits)
        }
        
        # Extract sum_income
        sum_income = 0.0
        if "sum_income" in aggs:
            sum_income = aggs["sum_income"].get("total", {}).get("value", 0.0) or 0.0
            result["aggs"]["sum_income"] = sum_income
        
        # Extract sum_expense
        sum_expense = 0.0
        if "sum_expense" in aggs:
            sum_expense = aggs["sum_expense"].get("total", {}).get("value", 0.0) or 0.0
            result["aggs"]["sum_expense"] = sum_expense
        
        # Calculate net client-side (income - expense)
        # This avoids scripted metrics which may not be allowed on Elastic Cloud
        if "sum_income" in result["aggs"] or "sum_expense" in result["aggs"]:
            result["aggs"]["net"] = sum_income - sum_expense
        
        # Extract count
        if "transaction_count" in aggs:
            result["aggs"]["count"] = aggs["transaction_count"].get("value", 0) or 0
        
        # Extract top merchants
        if "top_merchants" in aggs:
            merchants = []
            for bucket in aggs["top_merchants"].get("buckets", []):
                merchants.append({
                    "merchant": bucket.get("key", ""),
                    "count": bucket.get("doc_count", 0),
                    "total_amount": bucket.get("total_amount", {}).get("value", 0.0) or 0.0
                })
            result["aggs"]["top_merchants"] = merchants
        
        # Extract top categories
        if "top_categories" in aggs:
            categories = []
            for bucket in aggs["top_categories"].get("buckets", []):
                categories.append({
                    "category": bucket.get("key", ""),
                    "count": bucket.get("doc_count", 0),
                    "total_amount": bucket.get("total_amount", {}).get("value", 0.0) or 0.0
                })
            result["aggs"]["top_categories"] = categories
        
        # Extract currency (most common)
        currency = "USD"  # Default fallback
        if "currency_terms" in aggs:
            currency_buckets = aggs["currency_terms"].get("buckets", [])
            if currency_buckets:
                currency = currency_buckets[0].get("key", "USD")
            else:
                # No results with current filters - fetch currency from ANY transaction in the account
                try:
                    fallback_query = {"size": 1, "query": {"match_all": {}}, "_source": ["currency"]}
                    if plan.filters.accountNo:
                        fallback_query["query"] = {"term": {"accountNo": plan.filters.accountNo}}
                    
                    fallback_response = client.search(index=config.elastic_index_transactions, body=fallback_query)
                    fallback_hits = fallback_response.get("hits", {}).get("hits", [])
                    if fallback_hits:
                        currency = fallback_hits[0].get("_source", {}).get("currency", "USD")
                        log.debug(f"Retrieved currency from fallback query: {currency}")
                except Exception as e:
                    log.warning(f"Failed to retrieve currency from fallback query: {e}")
        
        result["currency"] = currency
        log.info(f"Aggregate filtered by text execution complete: {result['aggs']}, currency: {currency}")
        return result
        
    except Exception as e:
        log.exception(f"Error executing aggregate_filtered_by_text query: {e}")
        return {
            "intent": "aggregate_filtered_by_text",
            "error": str(e),
            "aggs": {},
            "provenance": []
        }

