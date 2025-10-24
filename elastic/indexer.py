"""
Elasticsearch index management and document indexing.

Provides functions for:
- Creating and managing Elasticsearch indices
- Bulk indexing documents
- Managing data streams for time-series data
- Creating index aliases
"""
from __future__ import annotations
import os
import time
from typing import Dict, Any, List, Optional

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError, NotFoundError, ElasticsearchException
from elasticsearch.helpers import bulk

from core.logger import get_logger
from .mappings import mapping_transactions, mapping_statements

log = get_logger("elastic/indexer")


def es_client() -> Elasticsearch:
    """
    Create Elasticsearch client using environment variables.
    
    Returns:
        Elasticsearch: Configured Elasticsearch client
        
    Raises:
        RuntimeError: If credentials are missing or client creation fails
        
    Note:
        Consider using elastic.client.es() for singleton client instead.
    """
    try:
        endpoint = os.getenv("ELASTIC_CLOUD_ENDPOINT")
        api_key = os.getenv("ELASTIC_API_KEY")
        
        if not endpoint or not api_key:
            error_msg = "Missing ELASTIC_CLOUD_ENDPOINT or ELASTIC_API_KEY"
            log.error(error_msg)
            raise RuntimeError(error_msg)
        
        log.debug(f"Creating Elasticsearch client for endpoint: {endpoint}")
        return Elasticsearch(endpoint, api_key=api_key, request_timeout=30)
        
    except RuntimeError:
        raise
    except Exception as e:
        log.error(f"Failed to create Elasticsearch client: {e}", exc_info=True)
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

def ensure_statements_index(index_name: str, *, vector_dim: Optional[int] = None):
    """
    Ensure statements index exists, creating it if necessary.
    
    Args:
        index_name: Name of the statements index
        vector_dim: Embedding dimension for vector field (optional)
        
    Raises:
        ElasticsearchException: If index creation fails
    """
    log.info(f"Ensuring statements index exists: {index_name}")
    
    try:
        es = es_client()
        
        if es.indices.exists(index=index_name):
            log.info(f"Statements index already exists: {index_name}")
            return
        
        log.info(f"Creating statements index: {index_name} with vector_dim={vector_dim}")
        mapping = mapping_statements(vector_dim)
        
        es.indices.create(index=index_name, body=mapping)
        
        log.info(f"Successfully created statements index: {index_name} (dim={vector_dim})")
        
    except ApiError as e:
        log.error(
            f"Elasticsearch API error creating statements index {index_name}: {e}",
            exc_info=True
        )
        raise
    except Exception as e:
        log.error(
            f"Unexpected error ensuring statements index {index_name}: {e}",
            exc_info=True
        )
        raise

def ensure_transactions_index(index_pattern: str, *, vector_dim: Optional[int] = None):
    """
    Ensure transactions data stream exists, creating it if necessary.
    
    Creates a composable index template and data stream for time-series
    transaction data with automatic rollover.
    
    Args:
        index_pattern: Base pattern for data stream (e.g., 'finsync-transactions')
        vector_dim: Embedding dimension for vector field (optional)
        
    Raises:
        ElasticsearchException: If data stream creation fails
        
    Note:
        Uses Elasticsearch data streams for efficient time-series data management.
    """
    log.info(f"Ensuring transactions data stream exists: {index_pattern}")
    
    try:
        es = es_client()
        template_name = f"{index_pattern}-template"
        
        # Create or update index template
        log.debug(f"Creating/updating index template: {template_name}")
        
        body = {
            "index_patterns": [f"{index_pattern}*"],
            "data_stream": {},
            "template": mapping_transactions(vector_dim),
            "priority": 200  # High priority to override default templates
        }
        
        es.indices.put_index_template(name=template_name, body=body)
        log.info(f"Index template '{template_name}' created/updated successfully")
        
        # Check if data stream exists
        try:
            stream_info = es.indices.get_data_stream(name=index_pattern)
            log.info(f"Transactions data stream already exists: {index_pattern}")
            log.debug(f"Data stream info: {stream_info}")
            
        except NotFoundError:
            log.info(f"Creating new transactions data stream: {index_pattern}")
            es.indices.create_data_stream(name=index_pattern)
            log.info(f"Successfully created transactions data stream: {index_pattern}")
            
    except ApiError as e:
        log.error(
            f"Elasticsearch API error ensuring transactions index {index_pattern}: {e}",
            exc_info=True
        )
        raise
    except Exception as e:
        log.error(
            f"Unexpected error ensuring transactions index {index_pattern}: {e}",
            exc_info=True
        )
        raise

def ensure_transaction_alias(alias_name: str, index_pattern: str):
    """
    Ensure a transaction alias exists.
    
    Creates an alias pointing to the transactions data stream or index pattern.
    Useful for abstracting index names in queries.
    
    Args:
        alias_name: Name of the alias to create
        index_pattern: Index pattern or data stream to point to
        
    Raises:
        ElasticsearchException: If alias creation fails
    """
    log.info(f"Ensuring transaction alias exists: {alias_name} -> {index_pattern}")
    
    try:
        es = es_client()
        
        if es.indices.exists_alias(name=alias_name):
            log.info(f"Transaction alias already exists: {alias_name}")
            
            # Log what indices the alias points to
            try:
                alias_info = es.indices.get_alias(name=alias_name)
                indices = list(alias_info.keys())
                log.debug(f"Alias '{alias_name}' points to: {indices}")
            except Exception as e:
                log.debug(f"Could not retrieve alias info: {e}")
            
            return
        
        log.info(f"Creating transaction alias: {alias_name} -> {index_pattern}")
        es.indices.put_alias(name=alias_name, index=index_pattern)
        log.info(f"Successfully created transaction alias: {alias_name}")
        
    except ApiError as e:
        log.error(
            f"Elasticsearch API error creating alias {alias_name}: {e}",
            exc_info=True
        )
        raise
    except Exception as e:
        log.error(
            f"Unexpected error ensuring alias {alias_name}: {e}",
            exc_info=True
        )
        raise

def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove None values from dictionary.
    
    Elasticsearch doesn't need explicit None values in documents.
    
    Args:
        d: Dictionary to clean
        
    Returns:
        Dict with None values removed
    """
    return {k: v for k, v in d.items() if v is not None}

def bulk_index(index: str, docs: List[Dict[str, Any]], *, id_field: Optional[str] = None) -> int:
    """
    Bulk index documents into Elasticsearch.
    
    Automatically detects data streams and uses appropriate operation type.
    Handles partial failures gracefully and logs detailed error information.
    
    Args:
        index: Target index or data stream name
        docs: List of document dictionaries to index
        id_field: Optional field name to use as document ID
        
    Returns:
        int: Number of successfully indexed documents
        
    Raises:
        ElasticsearchException: If bulk operation fails catastrophically
        
    Examples:
        >>> docs = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        >>> count = bulk_index("users", docs, id_field="id")
        >>> print(f"Indexed {count} documents")
    """
    start_time = time.time()
    
    if not docs:
        log.debug("No documents to index, skipping bulk operation")
        return 0
    
    log.info(
        f"Starting bulk index operation: index={index} "
        f"doc_count={len(docs)} id_field={id_field or 'auto'}"
    )
    
    try:
        es = es_client()
        
        # Detect if target is a data stream
        op_type = "index"
        is_data_stream = False
        
        try:
            info = es.indices.get_data_stream(name=index)
            if info and info.get("data_streams"):
                op_type = "create"
                is_data_stream = True
                log.debug(f"Target '{index}' is a data stream, using op_type=create")
        except NotFoundError:
            log.debug(f"Target '{index}' is a regular index, using op_type=index")
        
        # Prepare bulk actions
        actions = []
        total_size = 0
        
        for i, d in enumerate(docs):
            clean = _strip_none(d)
            
            # Estimate document size for logging
            total_size += len(str(clean))
            
            action = {
                "_op_type": op_type,
                "_index": index,
                "_source": clean
            }
            
            # Add document ID if specified
            if id_field and clean.get(id_field):
                action["_id"] = clean[id_field]
            
            actions.append(action)
        
        avg_size = total_size / len(actions) if actions else 0
        log.debug(
            f"Prepared {len(actions)} bulk actions: "
            f"total_size={total_size} bytes avg_size={avg_size:.0f} bytes/doc"
        )
        
        # Execute bulk operation
        ok, details = bulk(es, actions, raise_on_error=False, stats_only=False)
        
        # Parse results and collect failures
        failed = []
        if isinstance(details, list):
            for item in details:
                # Extract metadata from response
                meta = item.get("index") or item.get("create") or item.get("update") or {}
                status = meta.get("status", 200)
                
                if status >= 300:
                    failed.append(meta)
        
        # Log failures
        if failed:
            log.warning(f"Bulk operation had {len(failed)} failures out of {len(actions)} documents")
            
            # Log first 10 failures with details
            for i, f in enumerate(failed[:10]):
                log.error(
                    f"Bulk failure {i+1}: "
                    f"status={f.get('status')} "
                    f"id={f.get('_id', 'N/A')} "
                    f"error={f.get('error', 'Unknown error')}"
                )
            
            if len(failed) > 10:
                log.error(f"... and {len(failed) - 10} more failures (not shown)")
        
        # Calculate success rate
        success_rate = (ok / len(actions) * 100) if actions else 0
        elapsed = time.time() - start_time
        docs_per_sec = ok / elapsed if elapsed > 0 else 0
        
        log.info(
            f"Bulk index completed: index={index} "
            f"success={ok}/{len(actions)} ({success_rate:.1f}%) "
            f"failed={len(failed)} elapsed={elapsed:.2f}s "
            f"throughput={docs_per_sec:.0f} docs/sec"
        )
        
        return ok
        
    except ElasticsearchException as e:
        log.error(
            f"Elasticsearch error during bulk indexing to {index}: {e}",
            exc_info=True
        )
        raise
    except Exception as e:
        log.error(
            f"Unexpected error during bulk indexing to {index}: {e}",
            exc_info=True
        )
        raise
