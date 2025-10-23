from __future__ import annotations
from typing import List, Optional
from functools import lru_cache
from core.logger import get_logger
from core.config import config
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel

log = get_logger("embedding")

# Use the configured embedding model from config
EMBED_MODEL_NAME = config.vertex_model_embed

@lru_cache(maxsize=1)
def _load_model(project_id: str, location: str, model_name: str = EMBED_MODEL_NAME) -> TextEmbeddingModel:
    aiplatform.init(project=project_id, location=location)
    log.info(f"Loaded Vertex Embedding Model: {model_name}")
    return TextEmbeddingModel.from_pretrained(model_name)

def embed_texts(
    texts: List[str],
    *,
    project_id: str,
    location: str,
    model_name: str = EMBED_MODEL_NAME,
) -> List[List[float]]:
    """Returns one embedding per input text (same order)."""
    model = _load_model(project_id, location, model_name)
    # Vertex batches automatically; we call once for simplicity
    res = model.get_embeddings(texts)
    vectors = [e.values for e in res]
    if not vectors:
        raise RuntimeError("Empty embeddings returned from Vertex.")
    log.info(f"Generated embeddings: n={len(vectors)} dim={len(vectors[0])}")
    return vectors

def embedding_dim(
    *,
    project_id: str,
    location: str,
    model_name: str = EMBED_MODEL_NAME,
) -> int:
    """Infer dimension by embedding a tiny probe."""
    vec = embed_texts(["probe"], project_id=project_id, location=location, model_name=model_name)[0]
    return len(vec)
