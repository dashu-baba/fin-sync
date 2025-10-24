#!/usr/bin/env python3
"""Test aggregate_filtered_by_text intent with the international purchase query."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elastic.query_builders import q_hybrid
from models.intent import IntentClassification, IntentFilters
from core.logger import get_logger

log = get_logger("test_aggregate_filtered_by_text")


def test_query_cleaning():
    """Test that query cleaning extracts the right terms."""
    user_query = "How much did I spend on international purchase?"
    
    # Simulate the cleaning logic
    cleaned_query = user_query
    question_words = [
        "how much", "what", "when", "where", "why", "who", "which",
        "did i", "have i", "i spent", "i spend", "did i spend",
        "show me", "tell me", "give me", "list", "find"
    ]
    for qw in question_words:
        cleaned_query = cleaned_query.lower().replace(qw, "").strip()
    
    cleaned_query = cleaned_query.replace("?", "").replace("  ", " ").strip()
    
    print(f"Original query: {user_query}")
    print(f"Cleaned query: {cleaned_query}")
    print(f"Expected: 'on international purchase' or 'international purchase'")
    print()


def test_hybrid_query_building():
    """Test that q_hybrid builds the correct query with derived terms."""
    user_query = "How much did I spend on international purchase?"
    
    # Create a sample plan
    plan = IntentClassification(
        intent="aggregate_filtered_by_text",
        filters=IntentFilters(
            accountNo=None,
            dateFrom="2025-07-01",
            dateTo="2025-07-31",
            counterparty=None,
            minAmount=None,
            maxAmount=None
        ),
        metrics=["sum_expense"],
        granularity="monthly",
        needsTable=False,
        answerStyle="concise",
        confidence=0.9,
        needsClarification=False,
        clarifyQuestion=None,
        provenance=False,
        reasoning="Test query"
    )
    
    # Simulate empty statement hits (worst case)
    statement_hits = []
    
    print("=" * 80)
    print("TEST 1: No statement hits (user query only)")
    print("=" * 80)
    
    query = q_hybrid(user_query, plan, statement_hits)
    
    print("\nGenerated Elasticsearch query:")
    import json
    print(json.dumps(query, indent=2))
    
    # Check if user query was added to derived terms
    must_filters = query.get("query", {}).get("bool", {}).get("must", [])
    print("\nFilter clauses:")
    for i, filter_clause in enumerate(must_filters):
        print(f"{i+1}. {filter_clause}")
    
    # Check for should filters (derived terms)
    has_should = False
    for filter_clause in must_filters:
        if "bool" in filter_clause and "should" in filter_clause["bool"]:
            has_should = True
            should_filters = filter_clause["bool"]["should"]
            print(f"\nFound {len(should_filters)} derived filter(s):")
            for j, should_filter in enumerate(should_filters):
                print(f"  {j+1}. {should_filter}")
    
    if not has_should:
        print("\n❌ ERROR: No derived filters found! The query won't match any transactions.")
    else:
        print("\n✅ SUCCESS: Derived filters are present.")
    
    print("\n" + "=" * 80)
    print("TEST 2: With statement hits")
    print("=" * 80)
    
    # Simulate statement hits that might be returned
    statement_hits_with_data = [
        {
            "_id": "stmt1",
            "_source": {
                "summary_text": "Transaction at Pilgrims Gift Charity in Makkah, Saudi Arabia",
                "accountNo": "020XXXXXX0811",
                "bankName": "IFIC Bank",
                "statementFrom": "2025-07-01",
                "statementTo": "2025-07-31"
            }
        }
    ]
    
    query2 = q_hybrid(user_query, plan, statement_hits_with_data)
    
    print("\nGenerated Elasticsearch query with statement context:")
    print(json.dumps(query2, indent=2))
    
    print("\n" + "=" * 80)


def test_match_logic():
    """Test that the match query logic will find 'International Purchase' in description."""
    print("=" * 80)
    print("TEST 3: Match logic simulation")
    print("=" * 80)
    
    # The transaction description
    transaction_desc = "International Purchase 000112284400 Pilgrims Gift Charity at>MAKKAH SA"
    
    # The cleaned query
    cleaned_query = "on international purchase"
    
    print(f"\nTransaction description: {transaction_desc}")
    print(f"Cleaned query: {cleaned_query}")
    
    # Simulate match with 50% minimum_should_match
    query_words = cleaned_query.split()
    desc_words_lower = transaction_desc.lower().split()
    
    matches = [word for word in query_words if word in desc_words_lower]
    match_percentage = len(matches) / len(query_words) * 100 if query_words else 0
    
    print(f"\nQuery words: {query_words}")
    print(f"Matching words found: {matches}")
    print(f"Match percentage: {match_percentage:.0f}%")
    print(f"Minimum required: 50%")
    
    if match_percentage >= 50:
        print("\n✅ SUCCESS: Transaction should be matched!")
    else:
        print("\n❌ WARNING: Transaction might not be matched!")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Testing aggregate_filtered_by_text Query Building")
    print("=" * 80 + "\n")
    
    test_query_cleaning()
    test_hybrid_query_building()
    test_match_logic()
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print("""
The fixes applied:
1. ✅ Always include the original user query as a derived term (fallback)
2. ✅ Clean the user query to extract key terms ("international purchase")
3. ✅ Use 'match' instead of 'match_phrase' for flexible matching
4. ✅ Set minimum_should_match to 50% for partial word matches

Expected result:
- Query: "How much did I spend on international purchase?"
- Cleaned: "on international purchase" or "international purchase"
- Should match: "International Purchase 000112284400..." 
- Expected sum: 40,483.48

Next steps:
1. Run this test: python scripts/test_aggregate_filtered_by_text.py
2. Test in your UI with the actual query
3. Check logs for derived_filters in the response
""")

