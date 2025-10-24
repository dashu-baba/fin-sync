"""
Secret Manager integration for production deployments.
"""
from __future__ import annotations
import os
from typing import Any
from loguru import logger


def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """
    Retrieve secret from GCP Secret Manager or environment variable.
    
    In production with USE_SECRET_MANAGER=true, fetches from Secret Manager.
    Otherwise, falls back to environment variables.
    
    Args:
        secret_name: Name of the secret
        default: Default value if secret not found
        
    Returns:
        Secret value or default
    """
    from core.config import config
    
    use_secret_manager = os.getenv("USE_SECRET_MANAGER", "false").lower() == "true"
    
    # In production with Secret Manager enabled
    if use_secret_manager and config.environment == "production":
        try:
            from google.cloud import secretmanager
            
            client = secretmanager.SecretManagerServiceClient()
            project_id = config.gcp_project_id
            
            if not project_id:
                logger.warning("GCP_PROJECT_ID not set, falling back to env var")
                return os.getenv(secret_name, default)
            
            # Build the resource name
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            
            # Access the secret
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.debug(f"Retrieved secret '{secret_name}' from Secret Manager")
            return secret_value
            
        except Exception as e:
            logger.warning(f"Failed to fetch secret '{secret_name}' from Secret Manager: {e}")
            logger.info(f"Falling back to environment variable for '{secret_name}'")
            return os.getenv(secret_name, default)
    
    # Development or local mode - use environment variables
    return os.getenv(secret_name, default)


def load_secrets_into_env() -> None:
    """
    Load critical secrets from Secret Manager into environment variables.
    Call this during app initialization in production.
    """
    from core.config import config
    
    use_secret_manager = os.getenv("USE_SECRET_MANAGER", "false").lower() == "true"
    
    if not use_secret_manager or config.environment != "production":
        logger.info("Skipping Secret Manager - using environment variables")
        return
    
    # List of secrets to load
    secrets_to_load = [
        "ELASTIC_API_KEY",
        "ELASTIC_CLOUD_ENDPOINT",
    ]
    
    logger.info("Loading secrets from GCP Secret Manager...")
    
    for secret_name in secrets_to_load:
        # Only load if not already set (Cloud Run may inject some)
        if not os.getenv(secret_name):
            secret_value = get_secret(secret_name)
            if secret_value:
                os.environ[secret_name] = secret_value
                logger.info(f"Loaded secret: {secret_name}")
            else:
                logger.warning(f"Secret not found: {secret_name}")

