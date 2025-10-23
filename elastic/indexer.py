from __future__ import annotations
import os
from typing import Dict, Any, List
from elasticsearch import Elasticsearch, ApiError, NotFoundError
from elasticsearch.helpers import bulk
from core.logger import get_logger
from .mappings import mapping_transactions, mapping_statements

log = get_logger("indexer")


def es_client() -> Elasticsearch:
    try:
        endpoint = os.getenv("ELASTIC_CLOUD_ENDPOINT")
        api_key = os.getenv("ELASTIC_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError("Missing ELASTIC_CLOUD_ENDPOINT or ELASTIC_API_KEY.")
        return Elasticsearch(endpoint, api_key=api_key)
    except Exception as e:
        log.error(f"Failed to create Elasticsearch client: {e}")
        raise RuntimeError(f"Failed to create Elasticsearch client: {e}")


def ensure_index(index_name: str, *, vector_dim: int) -> None:
    es = es_client()
    if es.indices.exists(index=index_name):
        log.info(f"Index exists: {index_name}")
        return
    body = {
        "mappings": {
            "properties": {
                # top-level fields for quick filters
                "accountName": {"type": "keyword"},
                "accountNo": {"type": "keyword"},  # keep as string to preserve leading zeros
                "accountType": {"type": "keyword"},
                "statementFrom": {"type": "date"},
                "statementTo": {"type": "date"},
                "bankName": {"type": "keyword"},
                # flattened raw text (optional)
                "rawText": {"type": "text"},
                # vector for semantic search (Elasticsearch 8.x HNSW)
                "content_vector": {
                    "type": "dense_vector",
                    "dims": vector_dim,
                    "index": True,
                    "similarity": "cosine",
                },
                # nested transactions (numeric aggregations + keyword)
                "statements": {
                    "type": "nested",
                    "properties": {
                        "statementDate": {"type": "date"},
                        "statementAmount": {"type": "double"},
                        "statementType": {"type": "keyword"},
                        "statementDescription": {"type": "text"},
                        "statementBalance": {"type": "double"},
                        "statementNotes": {"type": "text"},
                    },
                },
            }
        },
    }
    es.indices.create(index=index_name, body=body)
    log.info(f"Created index: {index_name} (dim={vector_dim})")


def to_doc(parsed: Dict[str, Any], *, raw_text: str, vector: List[float]) -> Dict[str, Any]:
    doc = {
        "accountName": parsed.get("accountName"),
        "accountNo": parsed.get("accountNo"),
        "accountType": parsed.get("accountType"),
        "statementFrom": parsed.get("statementFrom"),
        "statementTo": parsed.get("statementTo"),
        "bankName": parsed.get("bankName"),
        "statements": parsed.get("statements", []),
        "rawText": raw_text,
        "content_vector": vector,
    }
    return doc


def index_docs(index_name: str, docs: List[Dict[str, Any]]) -> int:
    es = es_client()
    if not docs:
        return 0
    # Use bulk API for speed
    from elasticsearch.helpers import bulk

    actions = [{"_op_type": "index", "_index": index_name, "_source": d} for d in docs]
    success, _ = bulk(es, actions)
    log.info(f"Indexed {success} document(s) into {index_name}")
    return success

def ensure_statements_index(index_name: str, *, vector_dim: int | None = None):
    es = es_client()
    if es.indices.exists(index=index_name):
        log.info(f"Statements index exists: {index_name}")
        return
    es.indices.create(index=index_name, body=mapping_statements(vector_dim))
    log.info(f"Created statements index: {index_name} (dim={vector_dim})")

def ensure_transactions_index(index_pattern: str, *, vector_dim: int | None = None):
    """
    Use a data stream for transactions: {index_pattern} e.g. 'finsync-transactions'
    We create a composable template so writes to 'finsync-transactions' use a data stream.
    """
    es = es_client()
    template_name = f"{index_pattern}-template"
    body = {
        "index_patterns": [f"{index_pattern}*"],
        "data_stream": {},
        "template": mapping_transactions(vector_dim)
    }
    es.indices.put_index_template(name=template_name, body=body)
    # Create the data stream if absent
    try:
        es.indices.get_data_stream(name=index_pattern)
        log.info(f"Transactions data stream ready: {index_pattern}")
    except NotFoundError:
        es.indices.create_data_stream(name=index_pattern)
        log.info(f"Created data stream: {index_pattern}")

def ensure_transaction_alias(alias_name: str, index_pattern: str):
    """
    Ensure a transaction alias exists.
    Args:
        alias_name: The name of the alias
        index_pattern: The index pattern to alias
    """
    es = es_client()
    if es.indices.exists_alias(name=alias_name):
        log.info(f"Transaction alias exists: {alias_name}")
        return
    es.indices.put_alias(name=alias_name, index=index_pattern)
    log.info(f"Created transaction alias: {alias_name} for {index_pattern}")

def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}

def bulk_index(index: str, docs: List[Dict[str, Any]], *, id_field: str | None = None) -> int:
    if not docs:
        return 0
    es = es_client()
    log.info(f"Bulk indexing to {index} {' with id_field=' + id_field if id_field else ''}, {len(docs)} docs")
    # Detect if target is a data stream; data streams require op_type=create
    op_type = "index"
    try:
        info = es.indices.get_data_stream(name=index)
        if info and info.get("data_streams"):
            op_type = "create"
            log.info(f"Target '{index}' is a data stream; using op_type=create")
    except NotFoundError:
        pass
    actions = []
    for d in docs:
        clean = _strip_none(d)
        a = {"_op_type": op_type, "_index": index, "_source": clean}
        if id_field and clean.get(id_field):
            a["_id"] = clean[id_field]
        actions.append(a)
    try:
        ok, details = bulk(es, actions, raise_on_error=False, stats_only=False)
        # helpers.bulk may return a generator; when raise_on_error=False, it returns tuple
        # details can be a list of item responses; collect failures
        failed = []
        if isinstance(details, list):
            for item in details:
                # item looks like {"index": {"status": ..., "error": {...}, "_id": "..."}}
                meta = item.get("index") or item.get("create") or item.get("update") or {}
                status = meta.get("status", 200)
                if status >= 300:
                    failed.append(meta)
        if failed:
            for f in failed[:10]:
                log.error(f"Bulk index failure: status={f.get('status')} id={f.get('_id')} error={f.get('error')}")
            log.error(f"Total failures: {len(failed)} for index {index}")
        log.info(f"Indexed {ok} doc(s) into {index}")
        return ok
    except Exception as e:
        log.error(f"Bulk indexing to {index} failed: {e}")
        raise
