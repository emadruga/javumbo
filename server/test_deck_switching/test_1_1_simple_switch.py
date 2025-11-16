#!/usr/bin/env python3
"""
Test 1.1: Simple Switch and Return

Objective: Verify basic deck switching doesn't lose cards

This test reproduces the core "lost cards" bug by:
1. Creating 10 cards in the default deck
2. Creating a new deck "Test Deck B"
3. Switching to "Test Deck B"
4. Switching back to the default deck
5. Verifying all 10 cards are still visible

Expected Behavior: All 10 cards remain visible after deck switching
Bug Behavior: Some or all cards become invisible after switching back

Priority: CRITICAL - This is the primary bug reproduction test

Reference: docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md - Test Suite 1, Test 1.1
"""

import sys
import time
from test_deck_switching import (
    TestClient,
    TestResult,
    get_config,
    generate_test_username,
    format_test_header,
    assert_card_count,
    assert_cards_exist
)


def test_1_1_simple_switch_and_return(verbose=True):
    """
    Test 1.1: Simple Switch and Return

    This is THE CRITICAL TEST for reproducing the lost cards bug.

    Returns:
        TestResult object with test outcome
    """
    # Initialize test result tracker
    result = TestResult("1.1", "Simple Switch and Return")

    if verbose:
        print(format_test_header("1.1", "Simple Switch and Return"))
        print("Objective: Verify basic deck switching doesn't lose cards")
        print("Priority: CRITICAL")
        print()

    result.start()

    try:
        # Get configuration
        config = get_config()

        # Generate unique test user
        username = generate_test_username()
        password = config.default_password

        if verbose:
            print(f"Test User: {username}")
            print(f"Server: {config.base_url}")
            print()

        # Create and login test client
        client = TestClient(config.base_url, username, password, verbose=False)

        if verbose:
            print("STEP 1: Register and Login")
            print("-" * 70)

        client.register(name="Test User 1.1")
        client.login()

        if verbose:
            print(f"✓ Logged in as {username}")
            print()

        # Get default deck
        decks = client.get_decks()
        default_deck = decks[0]
        default_deck_id = default_deck['id']
        default_deck_name = default_deck['name']

        if verbose:
            print(f"STEP 2: Create 10 Cards in Default Deck")
            print("-" * 70)
            print(f"Default deck: {default_deck_name} (ID: {default_deck_id})")
            print()

        # Set current deck
        client.set_current_deck(default_deck_id)

        # Wait to avoid timestamp collision with sample cards
        if verbose:
            print("Waiting 2 seconds to avoid timestamp collisions...")
        time.sleep(2)

        # Create 10 test cards
        test_cards = []
        for i in range(1, 11):
            if verbose and i == 1:
                print("Creating 10 cards...")

            front = f"Test Deck A Card {i}"
            back = f"Answer {i}"

            card = client.add_card(front, back)
            test_cards.append({
                'front': front,
                'back': back,
                'card_id': card['card_id']
            })

            if verbose and i % 3 == 0:
                print(f"  Created {i}/10 cards...")

        if verbose:
            print(f"✓ All 10 cards created")
            print()

        # VERIFY: All 10 cards visible before switch
        if verbose:
            print("STEP 3: Verify All 10 Cards Before Switch")
            print("-" * 70)

        cards_before = client.get_deck_cards(default_deck_id)

        # Filter out sample cards - only count our test cards
        our_cards_before = [c for c in cards_before if any(tc['front'] == c['front'] for tc in test_cards)]

        if verbose:
            print(f"Total cards in deck: {len(cards_before)} (includes {len(cards_before) - 10} sample cards)")
            print(f"Our test cards: {len(our_cards_before)}")

        # Assert: Should have 10 cards
        assert_card_count(len(our_cards_before), 10, result)

        if len(our_cards_before) == 10:
            if verbose:
                print(f"✓ All 10 cards verified before switch")
                print()
        else:
            result.end(
                status="ERROR",
                error_message=f"Expected 10 cards before switch, found {len(our_cards_before)}",
                cards_before_switch=len(our_cards_before)
            )
            client.logout()
            return result

        # STEP 4: Create new deck "Test Deck B"
        if verbose:
            print("STEP 4: Create New Deck 'Test Deck B'")
            print("-" * 70)

        deck_b = client.create_deck("Test Deck B")
        deck_b_id = deck_b['id']

        if verbose:
            print(f"✓ Deck created: Test Deck B (ID: {deck_b_id})")
            print()

        # STEP 5: Switch to Deck B
        if verbose:
            print("STEP 5: Switch to Test Deck B")
            print("-" * 70)

        client.set_current_deck(deck_b_id)

        if verbose:
            print(f"✓ Switched to Test Deck B")
            print()

        # VERIFY: Deck B is empty
        cards_in_deck_b = client.get_deck_cards(deck_b_id)

        if verbose:
            print(f"Deck B cards: {len(cards_in_deck_b)}")

        assert_card_count(len(cards_in_deck_b), 0, result)

        if verbose:
            print(f"✓ Deck B is empty (as expected)")
            print()

        # STEP 6: Switch back to default deck
        if verbose:
            print("STEP 6: Switch Back to Default Deck")
            print("-" * 70)

        client.set_current_deck(default_deck_id)

        if verbose:
            print(f"✓ Switched back to {default_deck_name}")
            print()

        # CRITICAL CHECK: Verify all 10 cards still visible
        if verbose:
            print("STEP 7: CRITICAL VERIFICATION - Cards Still Visible?")
            print("-" * 70)

        cards_after = client.get_deck_cards(default_deck_id)

        # Filter to only our test cards
        our_cards_after = [c for c in cards_after if any(tc['front'] == c['front'] for tc in test_cards)]

        if verbose:
            print(f"Total cards in deck: {len(cards_after)}")
            print(f"Our test cards found: {len(our_cards_after)}")
            print()

        # Assert: Should still have 10 cards
        cards_match = assert_card_count(len(our_cards_after), 10, result)

        # Check each individual card
        all_cards_found = assert_cards_exist(
            cards_after,
            [tc['front'] for tc in test_cards],
            result
        )

        # Determine test outcome
        if len(our_cards_after) == 10 and all_cards_found:
            if verbose:
                print("=" * 70)
                print("✅ TEST PASSED")
                print("=" * 70)
                print("All 10 cards remain visible after deck switching")
                print("No bug detected - cards are preserved correctly")
                print()

            result.end(
                status="PASS",
                cards_before_switch=10,
                cards_after_switch=10,
                cards_lost=0
            )
        else:
            missing_count = 10 - len(our_cards_after)

            if verbose:
                print("=" * 70)
                print("🔴 BUG DETECTED!")
                print("=" * 70)
                print(f"Expected: 10 cards")
                print(f"Found: {len(our_cards_after)} cards")
                print(f"Missing: {missing_count} cards")
                print()
                print("This confirms the 'lost cards' bug reported by users!")
                print()

                # Show which cards are missing
                missing_cards = [tc for tc in test_cards if not any(c['front'] == tc['front'] for c in cards_after)]
                if missing_cards and verbose:
                    print("Missing cards:")
                    for mc in missing_cards[:5]:  # Show first 5
                        print(f"  - {mc['front']}")
                    if len(missing_cards) > 5:
                        print(f"  ... and {len(missing_cards) - 5} more")
                    print()

            result.end(
                status="FAIL",
                error_message=f"Cards missing after deck switch: expected 10, found {len(our_cards_after)}",
                cards_before_switch=10,
                cards_after_switch=len(our_cards_after),
                cards_lost=missing_count
            )

        # Cleanup
        client.logout()

    except Exception as e:
        if verbose:
            print(f"\n❌ Test Error: {e}")

        result.end(
            status="ERROR",
            error_message=str(e)
        )

    return result


def main():
    """
    Main entry point for running Test 1.1 standalone
    """
    import argparse

    parser = argparse.ArgumentParser(description='Test 1.1: Simple Switch and Return')
    parser.add_argument('--env', choices=['local', 'staging', 'production'],
                       help='Test environment (default: local)')
    parser.add_argument('--quiet', action='store_true',
                       help='Reduce output verbosity')

    args = parser.parse_args()

    # Set environment if specified
    if args.env:
        import os
        os.environ['TEST_ENV'] = args.env

    verbose = not args.quiet

    # Run the test
    result = test_1_1_simple_switch_and_return(verbose=verbose)

    # Print summary if not already printed
    if not verbose:
        print(result.to_string(verbose=True))

    # Exit with appropriate code
    if result.status == "PASS":
        sys.exit(0)
    elif result.status == "FAIL":
        sys.exit(1)  # Bug detected
    else:
        sys.exit(2)  # Error


if __name__ == "__main__":
    main()
