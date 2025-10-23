"""Elasticsearch query builders for different intent types."""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
from core.logger import get_logger
from models.intent import IntentClassification

log = get_logger("elastic/query_builders")


def q_aggregate(plan: IntentClassification) -> Dict[str, Any]:
    """
    Build ES query for aggregate intent.
    
    Returns query with:
    - size=0 (no document hits, only aggregations)
    - Filters: date range, accountNo, counterparty, min/maxAmount
    - Aggregations: sum_income, sum_expense, net, count, terms(merchant/category)
    
    Args:
        plan: IntentClassification with filters and metrics
        
    Returns:
        Elasticsearch query dict
    """
    log.info(f"Building aggregate query with filters: {plan.filters}")
    
    # Build filters
    must_filters: List[Dict[str, Any]] = []
    
    # Date range filter
    date_range: Dict[str, str] = {}
    if plan.filters.dateFrom:
        date_range["gte"] = plan.filters.dateFrom
    if plan.filters.dateTo:
        date_range["lte"] = plan.filters.dateTo
    
    if date_range:
        must_filters.append({
            "range": {
                "@timestamp": date_range
            }
        })
    
    # Account number filter
    if plan.filters.accountNo:
        must_filters.append({
            "term": {
                "accountNo": plan.filters.accountNo
            }
        })
    
    # Counterparty filter (match_phrase on description)
    if plan.filters.counterparty:
        must_filters.append({
            "match_phrase": {
                "description": plan.filters.counterparty
            }
        })
    
    # Amount range filters
    amount_range: Dict[str, float] = {}
    if plan.filters.minAmount is not None:
        amount_range["gte"] = plan.filters.minAmount
    if plan.filters.maxAmount is not None:
        amount_range["lte"] = plan.filters.maxAmount
    
    if amount_range:
        must_filters.append({
            "range": {
                "amount": amount_range
            }
        })
    
    # Build query body
    query_body: Dict[str, Any] = {
        "size": 0,  # No hits, only aggregations
        "query": {
            "bool": {
                "must": must_filters if must_filters else [{"match_all": {}}]
            }
        },
        "aggs": {}
    }
    
    # Build aggregations based on metrics
    metrics = plan.metrics or ["sum_income", "sum_expense", "net", "count"]
    
    # Income aggregation (sum of credit transactions)
    if "sum_income" in metrics or "income" in metrics:
        query_body["aggs"]["sum_income"] = {
            "filter": {"term": {"type": "credit"}},
            "aggs": {
                "total": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    # Expense aggregation (sum of debit transactions)
    if "sum_expense" in metrics or "expense" in metrics:
        query_body["aggs"]["sum_expense"] = {
            "filter": {"term": {"type": "debit"}},
            "aggs": {
                "total": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    # Net aggregation (we'll calculate from income - expense)
    # Or use script aggregation for signed amount
    if "net" in metrics:
        query_body["aggs"]["net"] = {
            "scripted_metric": {
                "init_script": "state.sum = 0",
                "map_script": """
                    if (doc['type.keyword'].value == 'credit') {
                        state.sum += doc['amount'].value
                    } else if (doc['type.keyword'].value == 'debit') {
                        state.sum -= doc['amount'].value
                    }
                """,
                "combine_script": "return state.sum",
                "reduce_script": "double sum = 0; for (s in states) { sum += s } return sum"
            }
        }
    
    # Count aggregation
    if "count" in metrics:
        query_body["aggs"]["transaction_count"] = {
            "value_count": {"field": "_id"}
        }
    
    # Top merchants (terms aggregation on description.raw)
    if "top_merchants" in metrics or "merchants" in metrics:
        query_body["aggs"]["top_merchants"] = {
            "terms": {
                "field": "description.raw",
                "size": 10,
                "order": {"total_amount": "desc"}
            },
            "aggs": {
                "total_amount": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    # Top categories (terms aggregation on category)
    if "top_categories" in metrics or "categories" in metrics:
        query_body["aggs"]["top_categories"] = {
            "terms": {
                "field": "category",
                "size": 10,
                "order": {"total_amount": "desc"}
            },
            "aggs": {
                "total_amount": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    log.debug(f"Built aggregate query: {query_body}")
    return query_body


def q_trend(plan: IntentClassification) -> Dict[str, Any]:
    """
    Build ES query for trend intent.
    
    Returns query with:
    - size=0
    - date_histogram aggregation with granularity from plan
    - Nested aggs: sum(signedAmount), sum(income), sum(expense)
    
    Args:
        plan: IntentClassification with filters and granularity
        
    Returns:
        Elasticsearch query dict
    """
    log.info(f"Building trend query with granularity: {plan.granularity}")
    
    # Build filters (reuse same logic as aggregate)
    must_filters: List[Dict[str, Any]] = []
    
    # Date range
    date_range: Dict[str, str] = {}
    if plan.filters.dateFrom:
        date_range["gte"] = plan.filters.dateFrom
    if plan.filters.dateTo:
        date_range["lte"] = plan.filters.dateTo
    
    if date_range:
        must_filters.append({"range": {"@timestamp": date_range}})
    
    # Account number
    if plan.filters.accountNo:
        must_filters.append({"term": {"accountNo": plan.filters.accountNo}})
    
    # Counterparty
    if plan.filters.counterparty:
        must_filters.append({"match_phrase": {"description": plan.filters.counterparty}})
    
    # Amount range
    amount_range: Dict[str, float] = {}
    if plan.filters.minAmount is not None:
        amount_range["gte"] = plan.filters.minAmount
    if plan.filters.maxAmount is not None:
        amount_range["lte"] = plan.filters.maxAmount
    
    if amount_range:
        must_filters.append({"range": {"amount": amount_range}})
    
    # Map granularity to calendar_interval
    granularity_map = {
        "daily": "1d",
        "weekly": "1w",
        "monthly": "1M"
    }
    calendar_interval = granularity_map.get(plan.granularity, "1M")
    
    query_body = {
        "size": 0,
        "query": {
            "bool": {
                "must": must_filters if must_filters else [{"match_all": {}}]
            }
        },
        "aggs": {
            "trend": {
                "date_histogram": {
                    "field": "@timestamp",
                    "calendar_interval": calendar_interval,
                    "format": "yyyy-MM-dd",
                    "min_doc_count": 0
                },
                "aggs": {
                    "income": {
                        "filter": {"term": {"type": "credit"}},
                        "aggs": {
                            "amount": {"sum": {"field": "amount"}}
                        }
                    },
                    "expense": {
                        "filter": {"term": {"type": "debit"}},
                        "aggs": {
                            "amount": {"sum": {"field": "amount"}}
                        }
                    },
                    "net": {
                        "scripted_metric": {
                            "init_script": "state.sum = 0",
                            "map_script": """
                                if (doc['type.keyword'].value == 'credit') {
                                    state.sum += doc['amount'].value
                                } else if (doc['type.keyword'].value == 'debit') {
                                    state.sum -= doc['amount'].value
                                }
                            """,
                            "combine_script": "return state.sum",
                            "reduce_script": "double sum = 0; for (s in states) { sum += s } return sum"
                        }
                    }
                }
            }
        }
    }
    
    log.debug(f"Built trend query: {query_body}")
    return query_body


def q_listing(plan: IntentClassification, limit: int = 50, sort_field: str = "@timestamp", sort_order: str = "desc") -> Dict[str, Any]:
    """
    Build ES query for listing intent.
    
    Returns query with:
    - size=limit
    - Filters applied
    - Sort by statementDate desc (default)
    - Returns full document _source
    
    Args:
        plan: IntentClassification with filters
        limit: Number of results to return
        sort_field: Field to sort by
        sort_order: Sort order (asc/desc)
        
    Returns:
        Elasticsearch query dict
    """
    log.info(f"Building listing query with limit={limit}, sort={sort_field} {sort_order}")
    
    # Build filters
    must_filters: List[Dict[str, Any]] = []
    
    # Date range
    date_range: Dict[str, str] = {}
    if plan.filters.dateFrom:
        date_range["gte"] = plan.filters.dateFrom
    if plan.filters.dateTo:
        date_range["lte"] = plan.filters.dateTo
    
    if date_range:
        must_filters.append({"range": {"@timestamp": date_range}})
    
    # Account number
    if plan.filters.accountNo:
        must_filters.append({"term": {"accountNo": plan.filters.accountNo}})
    
    # Counterparty
    if plan.filters.counterparty:
        must_filters.append({"match_phrase": {"description": plan.filters.counterparty}})
    
    # Amount range
    amount_range: Dict[str, float] = {}
    if plan.filters.minAmount is not None:
        amount_range["gte"] = plan.filters.minAmount
    if plan.filters.maxAmount is not None:
        amount_range["lte"] = plan.filters.maxAmount
    
    if amount_range:
        must_filters.append({"range": {"amount": amount_range}})
    
    query_body = {
        "size": limit,
        "query": {
            "bool": {
                "must": must_filters if must_filters else [{"match_all": {}}]
            }
        },
        "sort": [
            {sort_field: {"order": sort_order}}
        ],
        "_source": [
            "@timestamp",
            "amount",
            "type",
            "description",
            "category",
            "accountNo",
            "balance",
            "bankName",
            "currency"
        ]
    }
    
    log.debug(f"Built listing query: {query_body}")
    return query_body


def q_text_qa(user_query: str, filters: IntentFilters | None = None, size: int = 10) -> Dict[str, Any]:
    """
    Build ES query for text_qa intent - semantic Q&A on statements.
    
    Uses hybrid search: BM25 (keyword) + kNN (vector) for RRF fusion.
    This will be executed as two separate queries and results fused by RRF.
    
    Args:
        user_query: User's question
        filters: Optional filters (accountNo)
        size: Number of results
        
    Returns:
        Dict with 'keyword' and 'vector' queries to execute separately
    """
    log.info(f"Building text_qa queries for: {user_query}")
    
    filters = filters or IntentFilters()
    
    # Build filter clauses
    filter_clauses: List[Dict[str, Any]] = []
    
    if filters.accountNo:
        filter_clauses.append({"term": {"accountNo": filters.accountNo}})
    
    # Optional: date range on statements
    if filters.dateFrom or filters.dateTo:
        date_range: Dict[str, str] = {}
        if filters.dateFrom:
            date_range["gte"] = filters.dateFrom
        if filters.dateTo:
            date_range["lte"] = filters.dateTo
        
        # Use statementFrom/statementTo for filtering
        filter_clauses.append({
            "range": {"statementFrom": date_range}
        })
    
    # Keyword query (BM25) on text fields
    keyword_query = {
        "size": size,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": user_query,
                            "fields": [
                                "summary_text^2",  # Boost summary
                                "rawText",
                                "accountName",
                                "bankName"
                            ],
                            "type": "best_fields"
                        }
                    }
                ],
                "filter": filter_clauses if filter_clauses else []
            }
        },
        "_source": [
            "accountNo",
            "accountName", 
            "bankName",
            "statementFrom",
            "statementTo",
            "summary_text",
            "rawText",
            "meta"
        ]
    }
    
    # Vector query (kNN) - will need embedding
    # We'll handle embedding in the executor
    vector_query_template = {
        "size": size,
        "query": {
            "bool": {
                "filter": filter_clauses if filter_clauses else []
            }
        },
        "_source": [
            "accountNo",
            "accountName",
            "bankName", 
            "statementFrom",
            "statementTo",
            "summary_text",
            "rawText",
            "meta"
        ]
    }
    
    log.debug(f"Built text_qa queries: keyword={keyword_query}, vector_template={vector_query_template}")
    
    return {
        "keyword_query": keyword_query,
        "vector_query_template": vector_query_template,
        "user_query": user_query,
        "size": size
    }

