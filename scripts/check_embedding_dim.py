#!/usr/bin/env python3
"""
Check the actual embedding dimension of the configured model.
Run this to diagnose vector dimension mismatches.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import config
from core.logger import get_logger
from elastic.embedding import embedding_dim, EMBED_MODEL_NAME

log = get_logger("check_embedding")


def main():
    print("\n" + "=" * 60)
    print("Embedding Dimension Check")
    print("=" * 60)
    
    print(f"\n📋 Configuration:")
    print(f"   GCP Project: {config.gcp_project_id}")
    print(f"   Location: {config.gcp_location}")
    print(f"   Embedding Model: {EMBED_MODEL_NAME}")
    print(f"   Expected Dimension (config): {config.elastic_vector_dim}")
    
    print(f"\n🔍 Testing actual embedding dimension...")
    
    try:
        actual_dim = embedding_dim(
            project_id=config.gcp_project_id,
            location=config.gcp_location,
            model_name=EMBED_MODEL_NAME
        )
        
        print(f"   ✅ Actual Dimension: {actual_dim}")
        
        if actual_dim == config.elastic_vector_dim:
            print(f"\n✅ SUCCESS: Dimensions match!")
            print(f"   Your configuration is correct.")
        else:
            print(f"\n❌ MISMATCH DETECTED!")
            print(f"   Expected: {config.elastic_vector_dim}")
            print(f"   Actual:   {actual_dim}")
            print(f"\n🔧 To fix this, add to your .env file:")
            print(f"   ELASTIC_VECTOR_DIM={actual_dim}")
            print(f"\n   Then delete and recreate your indices:")
            print(f"   - finsync-statements")
            print(f"   - finsync-transactions (if using desc_vector)")
            
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        log.error(f"Failed to check embedding dimension: {e}")
        return 1
    
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

