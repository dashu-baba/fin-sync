def mapping_transactions(vector_dim: int | None = None):
    props = {
        "@timestamp": {"type": "date"},
        "accountNo": {"type": "keyword"},
        "bankName": {"type": "keyword"},
        "accountName": {"type": "keyword"},
        "type": {"type": "keyword"},
        "amount": {"type": "scaled_float", "scaling_factor": 100},
        "balance": {"type": "scaled_float", "scaling_factor": 100},
        "description": {"type": "text", "fields": {"raw": {"type": "keyword", "ignore_above": 256}}},
        "category": {"type": "keyword"},
        "currency": {"type": "keyword"},
        "sourceStatementId": {"type": "keyword"},
        "sourceFile": {"type": "keyword"},
    }
    if vector_dim:
        props["desc_vector"] = {"type": "dense_vector","dims": vector_dim,"index": True,"similarity":"cosine"}
    return {"mappings": {"properties": props}}

def mapping_statements(vector_dim: int):
    return {
        "mappings": {
            "properties": {
                "accountNo": {"type": "keyword"},
                "bankName": {"type": "keyword"},
                "accountName": {"type": "keyword"},
                "statementFrom": {"type": "date"},
                "statementTo": {"type": "date"},
                "summary_text": {"type": "text"},
                "summary_vector": {"type":"dense_vector","dims": vector_dim,"index": True,"similarity":"cosine"},
                "meta": {"type": "object", "enabled": True}
            }
        }
    }
