#!/usr/bin/env python3
"""
Create production indices in Elastic Cloud with proper mappings.
Run this before deploying to ensure indices exist.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from elastic.client import get_elastic_client
from elastic.mappings import (
    get_transaction_mappings,
    get_statement_mappings,
)
from core.config import config
from loguru import logger

# Load production environment
load_dotenv(".env.production", override=True)

def create_production_indices():
    """Create all production indices with proper mappings."""
    
    logger.info("🔧 Creating Production Indices")
    logger.info("=" * 60)
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Elastic Endpoint: {config.elastic_cloud_endpoint}")
    logger.info(f"Transaction Index: {config.elastic_index_transactions}")
    logger.info(f"Statement Index: {config.elastic_index_statements}")
    logger.info("=" * 60)
    
    # Get Elastic client
    client = get_elastic_client()
    
    if not client:
        logger.error("❌ Failed to connect to Elastic Cloud")
        return False
    
    logger.info("✅ Connected to Elastic Cloud")
    
    # Create transactions index (data stream)
    txn_index = config.elastic_index_transactions
    try:
        if client.indices.exists(index=txn_index):
            logger.info(f"✅ Transaction index '{txn_index}' already exists")
        else:
            logger.info(f"📦 Creating transaction index '{txn_index}'...")
            
            # For data streams, we need to create an index template first
            template_name = f"{txn_index}-template"
            
            # Check if template exists
            if not client.indices.exists_index_template(name=template_name):
                client.indices.put_index_template(
                    name=template_name,
                    index_patterns=[txn_index + "*"],
                    data_stream={},
                    template={
                        "mappings": get_transaction_mappings(),
                        "settings": {
                            "number_of_shards": 1,
                            "number_of_replicas": 1,
                        }
                    },
                    priority=200
                )
                logger.info(f"✅ Created index template '{template_name}'")
            
            # Create data stream
            client.indices.create_data_stream(name=txn_index)
            logger.info(f"✅ Created data stream '{txn_index}'")
    except Exception as e:
        logger.error(f"❌ Error creating transaction index: {e}")
        return False
    
    # Create statements index (regular index with dense_vector)
    stmt_index = config.elastic_index_statements
    try:
        if client.indices.exists(index=stmt_index):
            logger.info(f"✅ Statement index '{stmt_index}' already exists")
            
            # Verify it has the vector field
            mapping = client.indices.get_mapping(index=stmt_index)
            vector_field = config.elastic_vector_field
            if vector_field in mapping[stmt_index]['mappings'].get('properties', {}):
                logger.info(f"✅ Vector field '{vector_field}' exists")
            else:
                logger.warning(f"⚠️ Vector field '{vector_field}' not found in mapping")
        else:
            logger.info(f"📦 Creating statement index '{stmt_index}'...")
            client.indices.create(
                index=stmt_index,
                mappings=get_statement_mappings(),
                settings={
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                }
            )
            logger.info(f"✅ Created statement index '{stmt_index}'")
    except Exception as e:
        logger.error(f"❌ Error creating statement index: {e}")
        return False
    
    # Create alias for transaction view
    alias_name = config.elastic_alias_txn_view
    try:
        if client.indices.exists_alias(name=alias_name):
            logger.info(f"✅ Alias '{alias_name}' already exists")
        else:
            logger.info(f"🔗 Creating alias '{alias_name}'...")
            client.indices.put_alias(
                index=txn_index,
                name=alias_name
            )
            logger.info(f"✅ Created alias '{alias_name}' → '{txn_index}'")
    except Exception as e:
        logger.warning(f"⚠️ Could not create alias: {e}")
    
    logger.info("=" * 60)
    logger.info("✅ Production indices setup complete!")
    logger.info("=" * 60)
    
    # Show index stats
    try:
        txn_count = client.count(index=txn_index)['count']
        stmt_count = client.count(index=stmt_index)['count']
        
        logger.info(f"📊 Transaction documents: {txn_count}")
        logger.info(f"📊 Statement documents: {stmt_count}")
    except Exception as e:
        logger.warning(f"⚠️ Could not get document counts: {e}")
    
    return True


if __name__ == "__main__":
    success = create_production_indices()
    sys.exit(0 if success else 1)

