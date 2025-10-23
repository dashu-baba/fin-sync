#!/usr/bin/env python3
"""Test script for intent classification router."""
from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm.intent_router import classify_intent, classify_intent_safe
from core.logger import get_logger

log = get_logger("scripts/test_intent_router")


def test_basic_queries():
    """Test intent classification with various query types."""
    
    test_queries = [
        # Aggregate queries
        "What was my total spending last month?",
        "How much did I spend on groceries this year?",
        "Show me the average transaction amount",
        
        # Text QA
        "What is a debit transaction?",
        "Explain bank fees",
        
        # Listing
        "Show me the last 10 transactions",
        "List all bkash payments",
        
        # Trend
        "Show my monthly spending trend for 2024",
        "What's my income trend over the past 6 months?",
        
        # Aggregate with text filter
        "How much did I spend at merchants mentioned in statements?",
        "Total fees as mentioned in my bank statements",
    ]
    
    print("=" * 80)
    print("INTENT ROUTER TEST")
    print("=" * 80)
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {i}/{len(test_queries)}")
        print(f"Query: {query}")
        print("─" * 80)
        
        try:
            # Test with safe wrapper
            result = classify_intent_safe(query)
            
            if result:
                classification = result.classification
                print(f"✅ SUCCESS")
                print(f"  Intent: {classification.intent}")
                print(f"  Confidence: {classification.confidence:.2f}")
                print(f"  Processing time: {result.processing_time_ms:.0f}ms")
                
                if classification.filters.dateFrom or classification.filters.dateTo:
                    print(f"  Date range: {classification.filters.dateFrom} to {classification.filters.dateTo}")
                
                if classification.filters.counterparty:
                    print(f"  Counterparty: {classification.filters.counterparty}")
                
                if classification.metrics:
                    print(f"  Metrics: {', '.join(classification.metrics[:3])}{'...' if len(classification.metrics) > 3 else ''}")
                
                if classification.needsClarification:
                    print(f"  ⚠️  Needs clarification: {classification.clarifyQuestion}")
                
                if classification.reasoning:
                    print(f"  Reasoning: {classification.reasoning[:100]}...")
            else:
                print("❌ FAILED: classify_intent_safe returned None")
                
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            log.exception(f"Test failed for query: {query}")
        
        print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_basic_queries()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        log.exception(f"Test script failed: {e}")
        sys.exit(1)

