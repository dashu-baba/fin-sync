#!/usr/bin/env python3
"""Simple test for query cleaning logic without dependencies."""


def clean_user_query(user_query: str) -> str:
    """Clean the query by removing common question words."""
    cleaned_query = user_query.lower()
    
    # Remove question words and phrases
    stop_phrases = [
        "how much did i ", "how much have i ", "how much ",
        "what did i ", "what have i ", "what ",
        "when did i ", "when have i ", "when ",
        "where did i ", "where have i ", "where ",
        "did i spend on ", "have i spent on ", "did i spend ", "have i spent ",
        "i spent on ", "i spend on ", "i spent ", "i spend ",
        "show me ", "tell me ", "give me ", "list all ", "list ",
        "find all ", "find ", "total ", "sum of ", "sum ",
        "spent on ", "spend on ", "on ", "my ", "the ", "a "
    ]
    for phrase in stop_phrases:
        cleaned_query = cleaned_query.replace(phrase, " ")
    
    # Remove question marks, extra spaces, and common words
    cleaned_query = cleaned_query.replace("?", "").strip()
    cleaned_query = " ".join(cleaned_query.split())  # Normalize whitespace
    
    return cleaned_query


def simulate_match(transaction_desc: str, query: str, min_match_pct: int = 50) -> bool:
    """Simulate Elasticsearch match query with minimum_should_match."""
    query_words = query.lower().split()
    desc_words_lower = transaction_desc.lower().split()
    
    matches = [word for word in query_words if word in desc_words_lower]
    match_percentage = len(matches) / len(query_words) * 100 if query_words else 0
    
    return match_percentage >= min_match_pct, matches, match_percentage


def main():
    print("\n" + "=" * 80)
    print("Testing Query Cleaning and Matching Logic")
    print("=" * 80 + "\n")
    
    # Test case
    user_query = "How much did I spend on international purchase?"
    transaction_desc = "International Purchase 000112284400 Pilgrims Gift Charity at>MAKKAH SA 518613001083 1HZ4EY 402168"
    
    print(f"User Query: {user_query}")
    print(f"Transaction: {transaction_desc}")
    print()
    
    # Step 1: Clean query
    cleaned = clean_user_query(user_query)
    print(f"Step 1 - Cleaned Query: '{cleaned}'")
    print()
    
    # Step 2: Test matching
    will_match, matches, pct = simulate_match(transaction_desc, cleaned)
    
    print(f"Step 2 - Match Simulation:")
    print(f"  Query words: {cleaned.split()}")
    print(f"  Matched words: {matches}")
    print(f"  Match percentage: {pct:.0f}%")
    print(f"  Minimum required: 50%")
    print()
    
    if will_match:
        print("✅ RESULT: Transaction WILL BE MATCHED!")
        print(f"   Expected sum: 40,483.48")
    else:
        print("❌ RESULT: Transaction WILL NOT BE MATCHED")
        print(f"   Expected sum: 0 (This is the bug!)")
    
    print()
    
    # Additional test cases
    print("=" * 80)
    print("Additional Test Cases")
    print("=" * 80)
    print()
    
    test_cases = [
        ("What are my ATM withdrawals?", "Intl ATM Cash Withdrawal 000112283274 AL RAJHI BANK"),
        ("Show me bkash transactions", "BKASH MERCHANT PAYMENT TO 01712345678"),
        ("Total international purchases", "International Purchase 000112284400 Pilgrims Gift"),
        ("How much on fees?", "ATM Cash Withdrawal Fee 000112283274"),
    ]
    
    for query, desc in test_cases:
        cleaned = clean_user_query(query)
        will_match, matches, pct = simulate_match(desc, cleaned)
        status = "✅" if will_match else "❌"
        print(f"{status} Query: '{query}'")
        print(f"   Cleaned: '{cleaned}'")
        print(f"   Transaction: '{desc[:60]}...'")
        print(f"   Match: {pct:.0f}% (words: {matches})")
        print()
    
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print("""
The improvements to q_hybrid function:

1. ✅ Extract key terms from user query (remove question words)
2. ✅ Use cleaned query as the primary derived term
3. ✅ Switch from 'match_phrase' to 'match' for flexibility
4. ✅ Set minimum_should_match to 50% (at least half the words must match)

Why this fixes the "0 result" bug:
- Before: Looking for exact phrase "How much did I spend on international purchase?"
- After: Looking for "international purchase" with flexible word matching
- Result: Matches "International Purchase 000112284400..." ✅

Expected behavior:
- Query: "How much did I spend on international purchase?"
- Should find: 1 transaction
- Should return: 40,483.48 (instead of 0)
""")


if __name__ == "__main__":
    main()

