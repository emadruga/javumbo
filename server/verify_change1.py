#!/usr/bin/env python3
"""Verification script for Change 1: Empty Default Deck"""

import sqlite3
import json
import os
import sys

# Add server to path
sys.path.insert(0, os.path.dirname(__file__))

from app import init_anki_db, add_initial_flashcards, get_user_db_path

def verify_new_user_decks():
    """Verify that a new user gets MyFirstDeck (empty) and Verbal Tenses (108 cards)"""

    # Create a test database
    test_db = "/tmp/test_verify_user.db"

    # Clean up if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    print("Creating test database...")
    init_anki_db(test_db, user_name="Test User")
    add_initial_flashcards(test_db, "1700000000001", deck_id=2)

    print("\nConnecting to database...")
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Get collection
    cursor.execute("SELECT decks FROM col")
    decks_json = cursor.execute("SELECT decks FROM col").fetchone()[0]
    decks = json.loads(decks_json)

    print("\n" + "="*70)
    print("DECK STRUCTURE VERIFICATION")
    print("="*70)

    print(f"\nTotal Decks: {len(decks)}")

    for deck_id, deck_data in sorted(decks.items(), key=lambda x: int(x[0])):
        deck_name = deck_data['name']

        # Count cards in this deck
        cursor.execute("SELECT COUNT(*) FROM cards WHERE did = ?", (int(deck_id),))
        card_count = cursor.fetchone()[0]

        print(f"\nDeck #{deck_id}: {deck_name}")
        print(f"  Cards: {card_count}")
        print(f"  Description: {deck_data.get('desc', 'N/A')}")

        # Verification checks
        if int(deck_id) == 1:
            assert deck_name == "MyFirstDeck", f"Expected deck #1 to be 'MyFirstDeck', got '{deck_name}'"
            assert card_count == 0, f"Expected MyFirstDeck to be empty, got {card_count} cards"
            assert deck_data['desc'] == "Your first flashcard deck", f"Wrong description for MyFirstDeck"
            print("  ✅ VERIFIED: Empty default deck")

        elif int(deck_id) == 2:
            assert deck_name == "Verbal Tenses", f"Expected deck #2 to be 'Verbal Tenses', got '{deck_name}'"
            assert card_count == 108, f"Expected Verbal Tenses to have 108 cards, got {card_count}"
            assert "English verb tenses sample deck" in deck_data['desc'], f"Wrong description for Verbal Tenses"
            print("  ✅ VERIFIED: Sample cards deck with 108 cards")

    print("\n" + "="*70)
    print("✅ ALL VERIFICATIONS PASSED!")
    print("="*70)
    print("\nChange 1 implementation is correct:")
    print("  • Deck #1: MyFirstDeck (empty)")
    print("  • Deck #2: Verbal Tenses (108 sample cards)")
    print("")

    conn.close()

    # Clean up
    os.remove(test_db)

if __name__ == "__main__":
    verify_new_user_decks()
