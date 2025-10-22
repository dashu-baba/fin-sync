from elasticsearch import Elasticsearch
from core.config import config as cfg

_client = None

def es():
    global _client
    if _client is None:
        _client = Elasticsearch(
            cfg.elastic_cloud_endpoint,
            api_key=cfg.elastic_api_key,
            request_timeout=30,
            retry_on_timeout=True,
        )
    return _client
