"""Analytics queries using ES|QL for real-time aggregations."""
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
from elasticsearch import NotFoundError
from core.logger import get_logger
from core.config import config
from .client import es

log = get_logger("elastic/analytics")

# Index constants
SOURCE_INDEX = config.elastic_index_transactions


def ensure_monthly_rollup_transform() -> None:
    """
    No longer needed - we use ES|QL for real-time queries.
    Kept for backward compatibility.
    """
    log.info("Using ES|QL for analytics - no transform setup required")
    pass


def get_monthly_inflow_outflow(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    account_numbers: List[str] | None = None
) -> List[Dict[str, Any]]:
    """
    Query transactions using ES|QL for monthly inflow/outflow aggregation.
    
    Args:
        start_date: Filter results from this date (inclusive)
        end_date: Filter results to this date (inclusive)
        account_numbers: Filter by specific account numbers
        
    Returns:
        List of monthly aggregations with structure:
        {
            "accountNo": "1234567890",
            "month": "2024-01-01T00:00:00.000Z",
            "inflow": 5000.0,
            "outflow": 3000.0,
            "txCount": 45
        }
    """
    client = es()
    
    # Build ES|QL query
    esql_query_parts = [f"FROM {SOURCE_INDEX}"]
    
    # Add filters
    where_conditions = []
    if start_date:
        where_conditions.append(f'@timestamp >= "{start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")}"')
    if end_date:
        where_conditions.append(f'@timestamp <= "{end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")}"')
    if account_numbers and len(account_numbers) > 0:
        # ES|QL IN clause
        accounts_str = ", ".join([f'"{acc}"' for acc in account_numbers])
        where_conditions.append(f"accountNo IN ({accounts_str})")
    
    if where_conditions:
        esql_query_parts.append("| WHERE " + " AND ".join(where_conditions))
    
    # Add month calculation and aggregation
    esql_query_parts.extend([
        "| EVAL month = DATE_TRUNC(1 month, @timestamp)",
        "| STATS",
        "    inflow = SUM(CASE(type == \"credit\", amount, 0)),",
        "    outflow = SUM(CASE(type == \"debit\", amount, 0)),",
        "    txCount = COUNT(*)",
        "  BY month, accountNo",
        "| SORT month ASC, accountNo ASC"
    ])
    
    esql_query = "\n".join(esql_query_parts)
    
    log.info(f"Executing ES|QL query for monthly inflow/outflow")
    log.debug(f"ES|QL query:\n{esql_query}")
    
    # Execute ES|QL query
    try:
        response = client.esql.query(
            query=esql_query,
            format="json"
        )
        
        # Parse ES|QL response
        # ES|QL returns columns and values separately
        columns = response.get("columns", [])
        values = response.get("values", [])
        
        # Build column name to index mapping
        col_map = {col["name"]: idx for idx, col in enumerate(columns)}
        
        results = []
        for row in values:
            results.append({
                "month": row[col_map["month"]],
                "accountNo": row[col_map["accountNo"]],
                "inflow": float(row[col_map["inflow"]] or 0),
                "outflow": float(row[col_map["outflow"]] or 0),
                "txCount": int(row[col_map["txCount"]] or 0)
            })
        
        log.info(f"Retrieved {len(results)} monthly aggregation records via ES|QL")
        return results
        
    except Exception as e:
        log.error(f"Error executing ES|QL query: {e}")
        log.error(f"Query was:\n{esql_query}")
        # Return empty list instead of raising to allow UI to show "no data"
        return []


def get_available_accounts() -> List[str]:
    """
    Get list of unique account numbers using ES|QL.
    
    Returns:
        List of account numbers
    """
    client = es()
    
    esql_query = f"""
    FROM {SOURCE_INDEX}
    | STATS count = COUNT(*) BY accountNo
    | SORT accountNo ASC
    | LIMIT 100
    """
    
    try:
        response = client.esql.query(
            query=esql_query,
            format="json"
        )
        
        columns = response.get("columns", [])
        values = response.get("values", [])
        
        # Find accountNo column index
        col_map = {col["name"]: idx for idx, col in enumerate(columns)}
        account_idx = col_map.get("accountNo", 0)
        
        accounts = [row[account_idx] for row in values]
        
        log.info(f"Found {len(accounts)} unique accounts via ES|QL")
        return accounts
        
    except Exception as e:
        log.error(f"Error getting available accounts via ES|QL: {e}")
        return []

