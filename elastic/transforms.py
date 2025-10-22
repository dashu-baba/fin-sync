from __future__ import annotations
import time
from typing import Optional, Dict, Any
from elasticsearch import Elasticsearch, NotFoundError
from core.logger import get_logger
from .indexer import es_client

log = get_logger("transforms")

def _transform_body(
    source_index: str,
    dest_index: str,
    *,
    calendar_interval: str = "1M",
    frequency: str = "1h",
) -> Dict[str, Any]:
    """
    Monthly rollup per account using a Transform.
    Aggregations:
      - totalInflow: sum(amount) filtered by type=credit
      - totalOutflow: sum(amount) filtered by type=debit
      - avgTxn: average amount (all)
    """
    return {
        "source": {"index": source_index},
        "dest": {"index": dest_index},
        "pivot": {
            "group_by": {
                "accountNo": {"terms": {"field": "accountNo"}},
                "month": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": calendar_interval
                    }
                }
            },
            "aggregations": {
                "totalInflow": {
                    "filter": {"term": {"type": "credit"}},
                    "aggs": {"amount": {"sum": {"field": "amount"}}}
                },
                "totalOutflow": {
                    "filter": {"term": {"type": "debit"}},
                    "aggs": {"amount": {"sum": {"field": "amount"}}}
                },
                "avgTxn": {"avg": {"field": "amount"}}
            }
        },
        "frequency": frequency,
        "sync": {"time": {"field": "@timestamp"}},
        "settings": {"max_page_search_size": 5000},
        "description": "Monthly rollups per account for FinSync"
    }

def transform_exists(es: Elasticsearch, transform_id: str) -> bool:
    try:
        es.transform.get_transform(transform_id=transform_id)
        return True
    except NotFoundError:
        return False

def ensure_transform_monthly(
    transform_id: str,
    source_index: str,
    dest_index: str,
    *,
    calendar_interval: str = "1M",
    frequency: str = "1h",
) -> None:
    es = es_client()
    body = _transform_body(source_index, dest_index,
                           calendar_interval=calendar_interval,
                           frequency=frequency)
    if transform_exists(es, transform_id):
        log.info(f"Transform exists: {transform_id}")
    else:
        es.transform.put_transform(transform_id=transform_id, body=body)
        log.info(f"Created transform: {transform_id}")

def start_transform(transform_id: str) -> None:
    es = es_client()
    st = es.transform.get_transform_stats(transform_id=transform_id)
    state = st["transforms"][0]["state"]
    if state in ("stopped", "failed"):
        es.transform.start_transform(transform_id=transform_id)
        log.info(f"Started transform: {transform_id}")
    else:
        log.info(f"Transform already running: {transform_id} (state={state})")

def wait_for_first_checkpoint(transform_id: str, timeout_sec: int = 120) -> None:
    """
    Optional: wait until the transform completes its first checkpoint (initial backfill).
    """
    es = es_client()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        st = es.transform.get_transform_stats(transform_id=transform_id)
        stats = st["transforms"][0]
        cp = stats.get("checkpointing", {})
        last = cp.get("last", {})
        if last and last.get("checkpoint", 0) >= 1 and last.get("operations_behind", 0) == 0:
            log.info(f"Transform '{transform_id}' finished first checkpoint.")
            return
        time.sleep(2)
    log.warning(f"Timeout waiting for first checkpoint for transform '{transform_id}'.")
