"""Elasticsearch client singleton with connection management and health checking."""
from __future__ import annotations
from typing import Optional

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError

from core.config import config as cfg
from core.logger import get_logger

log = get_logger("elastic/client")

_client: Optional[Elasticsearch] = None


def es() -> Elasticsearch:
    """
    Get or create Elasticsearch client singleton.
    
    Returns:
        Elasticsearch: Configured Elasticsearch client
        
    Raises:
        RuntimeError: If Elastic Cloud credentials are not configured
        ESConnectionError: If connection to Elastic Cloud fails
    """
    global _client
    
    if _client is None:
        log.info("Initializing Elasticsearch client")
        
        # Validate configuration
        if not cfg.elastic_cloud_endpoint:
            error_msg = "ELASTIC_CLOUD_ENDPOINT is not configured"
            log.error(error_msg)
            raise RuntimeError(error_msg)
        
        if not cfg.elastic_api_key:
            error_msg = "ELASTIC_API_KEY is not configured"
            log.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            _client = Elasticsearch(
                cfg.elastic_cloud_endpoint,
                api_key=cfg.elastic_api_key,
                request_timeout=30,
                retry_on_timeout=True,
                max_retries=3,
            )
            
            # Test connection
            info = _client.info()
            cluster_name = info.get("cluster_name", "unknown")
            version = info.get("version", {}).get("number", "unknown")
            
            log.info(
                f"Elasticsearch client initialized successfully: "
                f"cluster={cluster_name} version={version}"
            )
            
        except ESConnectionError as e:
            log.error(
                f"Failed to connect to Elasticsearch: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            log.error(
                f"Unexpected error initializing Elasticsearch client: {type(e).__name__}: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to initialize Elasticsearch client: {e}")
    
    return _client


def reset_client() -> None:
    """
    Reset the Elasticsearch client singleton.
    
    Useful for testing or when connection needs to be refreshed.
    """
    global _client
    
    if _client is not None:
        log.info("Resetting Elasticsearch client")
        try:
            _client.close()
        except Exception as e:
            log.warning(f"Error closing Elasticsearch client: {e}")
        finally:
            _client = None


def health_check() -> bool:
    """
    Check if Elasticsearch cluster is healthy.
    
    Returns:
        bool: True if cluster is healthy, False otherwise
    """
    try:
        client = es()
        health = client.cluster.health()
        status = health.get("status", "unknown")
        
        log.debug(f"Elasticsearch cluster health: {status}")
        
        return status in ("green", "yellow")
        
    except Exception as e:
        log.error(f"Elasticsearch health check failed: {e}")
        return False
