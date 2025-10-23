"""Execute Elasticsearch queries and transform responses for different intents."""
from __future__ import annotations
from typing import Dict, Any, List
from core.logger import get_logger
from core.config import config
from models.intent import IntentClassification, IntentResponse
from elastic.client import es
from elastic.query_builders import q_aggregate, q_trend, q_listing

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
        
        log.info(f"Aggregate execution complete: {result['aggs']}")
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
            buckets.append({
                "date": bucket.get("key_as_string", ""),
                "timestamp": bucket.get("key", 0),
                "income": bucket.get("income", {}).get("amount", {}).get("value", 0.0) or 0.0,
                "expense": bucket.get("expense", {}).get("amount", {}).get("value", 0.0) or 0.0,
                "net": bucket.get("net", {}).get("value", 0.0) or 0.0,
                "count": bucket.get("doc_count", 0)
            })
        
        result = {
            "intent": "trend",
            "granularity": plan.granularity,
            "buckets": buckets,
            "filters_applied": {
                "dateFrom": plan.filters.dateFrom,
                "dateTo": plan.filters.dateTo,
                "accountNo": plan.filters.accountNo,
                "counterparty": plan.filters.counterparty,
                "minAmount": plan.filters.minAmount,
                "maxAmount": plan.filters.maxAmount
            }
        }
        
        log.info(f"Trend execution complete: {len(buckets)} buckets")
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

