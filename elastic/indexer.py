from __future__ import annotations
import os
from typing import Dict, Any, List
from elasticsearch import Elasticsearch, ApiError
from core.logger import get_logger

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
