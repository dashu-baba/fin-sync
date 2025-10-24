"""Elasticsearch query builders for different intent types."""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
from core.logger import get_logger
from models.intent import IntentClassification, IntentFilters

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
    
    # Counterparty filter (flexible match on description)
    if plan.filters.counterparty:
        # Use match with "or" operator and minimum_should_match for flexible matching
        # This matches if most key words appear, not requiring ALL words
        must_filters.append({
            "match": {
                "description": {
                    "query": plan.filters.counterparty,
                    "operator": "or",  # Any word can match
                    "minimum_should_match": "50%",  # At least 50% of words should match
                    "fuzziness": "AUTO"  # Allow minor typos/variations
                }
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
    
    # Net aggregation
    # Note: Net is calculated client-side (sum_income - sum_expense) to avoid
    # scripted metrics which may not be allowed on Elastic Cloud
    # No aggregation needed here - will be computed in executor
    
    # Count aggregation
    if "count" in metrics:
        query_body["aggs"]["transaction_count"] = {
            "value_count": {"field": "@timestamp"}
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
    
    # Always add currency aggregation to determine the currency to display
    query_body["aggs"]["currency_terms"] = {
        "terms": {
            "field": "currency",
            "size": 1  # Get the most common currency
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
    
    # Counterparty filter (flexible match on description)
    if plan.filters.counterparty:
        # Use match instead of match_phrase for more flexible matching
        must_filters.append({
            "match": {
                "description": {
                    "query": plan.filters.counterparty,
                    "operator": "or",
                    "minimum_should_match": "50%",
                    "fuzziness": "AUTO"
                }
            }
        })
    
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
                    }
                    # Note: net will be calculated client-side (income - expense)
                    # Removed scripted_metric due to Elastic Cloud security restrictions
                }
            },
            # Always add currency aggregation to determine the currency to display
            "currency_terms": {
                "terms": {
                    "field": "currency",
                    "size": 1  # Get the most common currency
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
    
    # Counterparty filter (flexible match on description)
    if plan.filters.counterparty:
        # Use match instead of match_phrase for more flexible matching
        must_filters.append({
            "match": {
                "description": {
                    "query": plan.filters.counterparty,
                    "operator": "or",
                    "minimum_should_match": "50%",
                    "fuzziness": "AUTO"
                }
            }
        })
    
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


def q_hybrid(user_query: str, plan: IntentClassification, statement_hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build ES query for aggregate_filtered_by_text intent.
    
    This is step 2 of a two-step process:
    1. Text QA found relevant statements
    2. Now build aggregate query using derived filters from statements
    
    Derives merchant filters from statement hits and applies them to transaction aggregation.
    
    Args:
        user_query: Original user query
        plan: IntentClassification with filters
        statement_hits: Results from text_qa search on statements
        
    Returns:
        Aggregate query with derived merchant/counterparty filters
    """
    log.info(f"Building hybrid aggregate query with {len(statement_hits)} statement hits")
    
    # Extract merchant/counterparty terms from statement hits
    derived_merchants = set()
    derived_terms = []
    
    for hit in statement_hits[:5]:  # Use top 5 statement hits
        source = hit.get("_source", {})
        
        # Try to extract merchant names from summary text or rawText
        summary = source.get("summary_text", "") or source.get("rawText", "")
        
        # Simple extraction: look for common patterns
        # This could be enhanced with NER or more sophisticated extraction
        if summary:
            # Add summary text as search term
            derived_terms.append(summary[:100])  # Use first 100 chars
    
    # IMPORTANT: Always include the original user query as a search term
    # This ensures we match transactions even if statement extraction fails
    if user_query and user_query.strip():
        # Clean the query by removing common question words for better matching
        cleaned_query = user_query.lower()
        
        # Remove question words and phrases
        stop_phrases = [
            "how much did i ", "how much have i ", "how much ",
            "what did i ", "what have i ", "what ",
            "when did i ", "when have i ", "when ",
            "where did i ", "where have i ", "where ",
            "did i spend on ", "have i spent on ", "did i spend ", "have i spent ",
            "i spent on ", "i spend on ", "i spent ", "i spend ",
            "show me ", "tell me ", "give me ", "list all ", "list ",
            "find all ", "find ", "total ", "sum of ", "sum ",
            "spent on ", "spend on ", "on ", "my ", "the ", "a "
        ]
        for phrase in stop_phrases:
            cleaned_query = cleaned_query.replace(phrase, " ")
        
        # Remove question marks, extra spaces, and common words
        cleaned_query = cleaned_query.replace("?", "").strip()
        cleaned_query = " ".join(cleaned_query.split())  # Normalize whitespace
        
        if cleaned_query and len(cleaned_query) > 2:  # Only use if meaningful
            derived_terms.insert(0, cleaned_query)  # Add cleaned query as first term
    
    # Build filters (same as q_aggregate but with additional derived filters)
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
    
    # Derived filters from statement hits
    # Use match_phrase on description with terms from statements
    should_filters: List[Dict[str, Any]] = []
    
    if derived_terms:
        for term in derived_terms[:3]:  # Use top 3 terms
            if term.strip():
                # Use match (not match_phrase) for more flexible matching
                # This allows partial matches and is case-insensitive
                should_filters.append({
                    "match": {
                        "description": {
                            "query": term,
                            "operator": "or",  # Match any word in the query
                            "minimum_should_match": "50%"  # At least 50% of words should match
                        }
                    }
                })
    
    # Fallback: use counterparty from plan if no derived terms
    if not should_filters and plan.filters.counterparty:
        should_filters.append({
            "match_phrase": {
                "description": plan.filters.counterparty
            }
        })
    
    # Add should filters as a bool query
    if should_filters:
        must_filters.append({
            "bool": {
                "should": should_filters,
                "minimum_should_match": 1
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
    
    # Build query body (same structure as q_aggregate)
    query_body: Dict[str, Any] = {
        "size": 0,  # No hits, only aggregations
        "query": {
            "bool": {
                "must": must_filters if must_filters else [{"match_all": {}}]
            }
        },
        "aggs": {}
    }
    
    # Build aggregations (same as q_aggregate)
    metrics = plan.metrics or ["sum_income", "sum_expense", "net", "count"]
    
    # Income aggregation
    if "sum_income" in metrics or "income" in metrics:
        query_body["aggs"]["sum_income"] = {
            "filter": {"term": {"type": "credit"}},
            "aggs": {
                "total": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    # Expense aggregation
    if "sum_expense" in metrics or "expense" in metrics:
        query_body["aggs"]["sum_expense"] = {
            "filter": {"term": {"type": "debit"}},
            "aggs": {
                "total": {
                    "sum": {"field": "amount"}
                }
            }
        }
    
    # Net aggregation
    # Note: Net is calculated client-side (sum_income - sum_expense) to avoid
    # scripted metrics which may not be allowed on Elastic Cloud
    # No aggregation needed here - will be computed in executor
    
    # Count aggregation
    if "count" in metrics:
        query_body["aggs"]["transaction_count"] = {
            "value_count": {"field": "@timestamp"}
        }
    
    # Top merchants
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
    
    # Top categories
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
    
    log.debug(f"Built hybrid aggregate query with derived filters")
    return query_body

