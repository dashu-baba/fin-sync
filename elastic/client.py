from elasticsearch import Elasticsearch
from core.config import cfg

_client = None

def es():
    global _client
    if _client is None:
        _client = Elasticsearch(
            cloud_id=cfg.elastic_cloud_endpoint,
            api_key=cfg.elastic_api_key,
            request_timeout=30,
            retry_on_timeout=True,
        )
    return _client
