#!/usr/bin/env python3
"""
Delete and recreate indices with correct vector dimensions.
CAUTION: This will delete all existing data in the indices!
"""
from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import config
from core.logger import get_logger
from elastic.client import es
from elastic.indexer import ensure_statements_index, ensure_transactions_index
from elastic.embedding import embedding_dim, EMBED_MODEL_NAME

log = get_logger("fix_indices")


def main():
    print("\n" + "=" * 60)
    print("Fix Elasticsearch Indices")
    print("=" * 60)
    
    # Get actual embedding dimension
    print(f"\n🔍 Detecting embedding dimension...")
    try:
        actual_dim = embedding_dim(
            project_id=config.gcp_project_id,
            location=config.gcp_location,
            model_name=EMBED_MODEL_NAME
        )
        print(f"   Detected dimension: {actual_dim}")
    except Exception as e:
        print(f"   ❌ Failed to detect dimension: {e}")
        return 1
    
    client = es()
    
    # Check which indices exist
    statements_exists = client.indices.exists(index=config.elastic_index_statements)
    
    print(f"\n📊 Current state:")
    print(f"   Statements index exists: {statements_exists}")
    
    if not statements_exists:
        print(f"\n✅ No indices to fix. Creating fresh indices...")
        ensure_statements_index(config.elastic_index_statements, vector_dim=actual_dim)
        ensure_transactions_index(config.elastic_index_transactions, vector_dim=actual_dim)
        print(f"   ✅ Indices created successfully!")
        return 0
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will DELETE existing data!")
    print(f"   Indices to be deleted and recreated:")
    if statements_exists:
        print(f"   - {config.elastic_index_statements}")
    
    response = input(f"\n   Type 'DELETE' to confirm: ")
    
    if response != "DELETE":
        print(f"\n❌ Aborted. No changes made.")
        return 1
    
    # Delete indices
    print(f"\n🗑️  Deleting indices...")
    if statements_exists:
        client.indices.delete(index=config.elastic_index_statements)
        print(f"   Deleted: {config.elastic_index_statements}")
    
    # Recreate with correct dimensions
    print(f"\n🔨 Recreating indices with dimension={actual_dim}...")
    ensure_statements_index(config.elastic_index_statements, vector_dim=actual_dim)
    print(f"   Created: {config.elastic_index_statements}")
    
    ensure_transactions_index(config.elastic_index_transactions, vector_dim=actual_dim)
    print(f"   Created: {config.elastic_index_transactions}")
    
    print(f"\n✅ SUCCESS! Indices recreated with correct dimensions.")
    print(f"\n📝 Next steps:")
    print(f"   1. Add to your .env file: ELASTIC_VECTOR_DIM={actual_dim}")
    print(f"   2. Re-run your document parsing to re-index data")
    print(f"   3. Test the Analytics tab")
    
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

