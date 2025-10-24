"""
Text embedding generation using Vertex AI.

Provides functions to:
- Generate text embeddings using Vertex AI models
- Cache embedding model instances
- Determine embedding dimensions
"""
from __future__ import annotations
import time
from typing import List
from functools import lru_cache

from google.cloud import aiplatform
from google.api_core.exceptions import GoogleAPIError
from vertexai.language_models import TextEmbeddingModel

from core.logger import get_logger
from core.config import config

log = get_logger("elastic/embedding")

# Use the configured embedding model from config
EMBED_MODEL_NAME = config.vertex_model_embed
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


@lru_cache(maxsize=1)
def _load_model(project_id: str, location: str, model_name: str = EMBED_MODEL_NAME) -> TextEmbeddingModel:
    """
    Load and cache Vertex AI embedding model.
    
    Uses LRU cache to avoid reloading the model on every call.
    
    Args:
        project_id: GCP project ID
        location: GCP region (e.g., 'us-central1')
        model_name: Embedding model name
        
    Returns:
        TextEmbeddingModel: Loaded embedding model
        
    Raises:
        RuntimeError: If model initialization fails
    """
    try:
        log.info(
            f"Initializing Vertex AI embedding model: "
            f"project={project_id} location={location} model={model_name}"
        )
        
        aiplatform.init(project=project_id, location=location)
        model = TextEmbeddingModel.from_pretrained(model_name)
        
        log.info(f"Vertex AI embedding model loaded successfully: {model_name}")
        return model
        
    except Exception as e:
        log.error(
            f"Failed to load Vertex AI embedding model: "
            f"model={model_name} error={e}",
            exc_info=True
        )
        raise RuntimeError(f"Failed to load embedding model: {e}")


def embed_texts(
    texts: List[str],
    *,
    project_id: str,
    location: str,
    model_name: str = EMBED_MODEL_NAME,
) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.
    
    Automatically batches requests to Vertex AI and includes retry logic.
    Returns embeddings in the same order as input texts.
    
    Args:
        texts: List of text strings to embed
        project_id: GCP project ID
        location: GCP region
        model_name: Embedding model name (default from config)
        
    Returns:
        List of embedding vectors (list of floats for each text)
        
    Raises:
        ValueError: If texts list is empty or contains invalid data
        RuntimeError: If embedding generation fails after retries
        
    Examples:
        >>> embeddings = embed_texts(
        ...     ["Hello world", "Goodbye"],
        ...     project_id="my-project",
        ...     location="us-central1"
        ... )
        >>> len(embeddings)
        2
        >>> len(embeddings[0])
        768  # Dimension depends on model
    """
    start_time = time.time()
    
    # Validate input
    if not texts:
        error_msg = "texts list cannot be empty"
        log.error(error_msg)
        raise ValueError(error_msg)
    
    if not all(isinstance(t, str) for t in texts):
        error_msg = "All items in texts must be strings"
        log.error(error_msg)
        raise ValueError(error_msg)
    
    # Remove empty strings and log warning
    non_empty_texts = [t for t in texts if t.strip()]
    if len(non_empty_texts) < len(texts):
        log.warning(
            f"Filtered out {len(texts) - len(non_empty_texts)} empty strings from embedding input"
        )
    
    if not non_empty_texts:
        error_msg = "No non-empty texts to embed"
        log.error(error_msg)
        raise ValueError(error_msg)
    
    log.info(
        f"Generating embeddings: count={len(non_empty_texts)} "
        f"model={model_name} total_chars={sum(len(t) for t in non_empty_texts)}"
    )
    
    # Retry logic for transient errors
    last_error = None
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            model = _load_model(project_id, location, model_name)
            
            # Generate embeddings (Vertex AI handles batching internally)
            response = model.get_embeddings(non_empty_texts)
            
            # Extract vectors
            vectors = [embedding.values for embedding in response]
            
            if not vectors:
                raise RuntimeError("Empty embeddings returned from Vertex AI")
            
            # Validate all embeddings have same dimension
            dimensions = [len(v) for v in vectors]
            if len(set(dimensions)) > 1:
                log.warning(
                    f"Inconsistent embedding dimensions: {set(dimensions)}"
                )
            
            elapsed = time.time() - start_time
            log.info(
                f"Generated embeddings successfully: "
                f"count={len(vectors)} dim={len(vectors[0])} "
                f"elapsed={elapsed:.2f}s attempt={attempt + 1}"
            )
            
            return vectors
            
        except GoogleAPIError as e:
            last_error = e
            log.warning(
                f"Vertex AI API error (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}): {e}"
            )
            
            # Retry on transient errors
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                log.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            
        except Exception as e:
            log.error(
                f"Unexpected error generating embeddings: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to generate embeddings: {e}")
    
    # All retries exhausted
    error_msg = f"Failed to generate embeddings after {MAX_RETRY_ATTEMPTS} attempts: {last_error}"
    log.error(error_msg)
    raise RuntimeError(error_msg)


def embedding_dim(
    *,
    project_id: str,
    location: str,
    model_name: str = EMBED_MODEL_NAME,
) -> int:
    """
    Determine embedding dimension by generating a probe embedding.
    
    Creates a small test embedding to infer the dimension size.
    Result is typically cached by the embedding model.
    
    Args:
        project_id: GCP project ID
        location: GCP region
        model_name: Embedding model name
        
    Returns:
        int: Embedding dimension (e.g., 768 for gecko models)
        
    Raises:
        RuntimeError: If dimension cannot be determined
        
    Examples:
        >>> dim = embedding_dim(
        ...     project_id="my-project",
        ...     location="us-central1"
        ... )
        >>> dim
        768
    """
    try:
        log.debug(f"Determining embedding dimension for model: {model_name}")
        
        probe_vec = embed_texts(
            ["probe"],
            project_id=project_id,
            location=location,
            model_name=model_name
        )[0]
        
        dimension = len(probe_vec)
        log.info(f"Embedding dimension determined: {dimension} for model {model_name}")
        
        return dimension
        
    except Exception as e:
        log.error(
            f"Failed to determine embedding dimension: {e}",
            exc_info=True
        )
        raise RuntimeError(f"Failed to determine embedding dimension: {e}")
