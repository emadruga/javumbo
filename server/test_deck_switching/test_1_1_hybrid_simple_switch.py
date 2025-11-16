#!/usr/bin/env python3
"""
Hybrid E2E Test 1.1: Simple Switch and Return

This test uses a HYBRID approach:
- API for registration/login/card creation (fast, reliable)
- Selenium for deck switching UI interactions (where the bug occurs)

This approach gives us the best of both worlds:
1. Fast and reliable setup via API
2. Real UI testing for the bug-prone deck switching

The bug manifests in the FRONTEND when users switch decks, so we need
to test the actual React UI for deck switching operations.
"""

import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from test_deck_switching import (
    TestClient,
    TestResult,
    generate_test_username,
    format_test_header,
    get_config
)


def test_1_1_hybrid_simple_switch(verbose=True, headless=True):
    """
    Hybrid Test 1.1: API setup + Selenium deck switching

    This is THE test that should reproduce the lost cards bug!
    """
    result = TestResult("1.1-Hybrid", "Simple Switch and Return (Hybrid E2E)")

    if verbose:
        print(format_test_header("1.1-Hybrid", "Simple Switch and Return (Hybrid E2E)"))
        print("Method: API for setup + Selenium for UI testing")
        print("Focus: Deck switching through React UI")
        print()

    result.start()

    driver = None
    api_client = None

    try:
        # ============================================================
        # PHASE 1: API Setup (Fast and Reliable)
        # ============================================================

        config = get_config()
        username = generate_test_username()
        password = config.default_password

        if verbose:
            print("PHASE 1: Setup via API")
            print("=" * 70)
            print(f"Test User: {username}")
            print(f"API Server: {config.base_url}")
            print()

        # Create API client
        api_client = TestClient(config.base_url, username, password, verbose=False)

        # Register via API
        if verbose:
            print("Step 1: Register user via API...")
        api_client.register(name="Hybrid Test User")

        # Login via API
        if verbose:
            print("Step 2: Login via API...")
        api_client.login()

        # Get default deck
        decks = api_client.get_decks()
        default_deck = decks[0]
        default_deck_id = default_deck['id']
        default_deck_name = default_deck['name']

        if verbose:
            print(f"✓ Default deck: {default_deck_name} (ID: {default_deck_id})")

        # Set current deck
        api_client.set_current_deck(default_deck_id)

        # Wait to avoid timestamp collisions
        time.sleep(2)

        # Create 10 test cards via API
        if verbose:
            print("Step 3: Creating 10 test cards via API...")

        test_cards = []
        for i in range(1, 11):
            front = f"Hybrid Test Card {i}"
            back = f"Hybrid Answer {i}"
            card = api_client.add_card(front, back)
            test_cards.append({
                'front': front,
                'back': back,
                'card_id': card['card_id']
            })

            if verbose and i % 3 == 0:
                print(f"  Created {i}/10 cards...")

        if verbose:
            print("✓ All 10 cards created via API")
            print()

        # Verify cards via API before UI test
        cards_via_api = api_client.get_deck_cards(default_deck_id)
        our_cards_via_api = [c for c in cards_via_api if any(tc['front'] == c['front'] for tc in test_cards)]

        if verbose:
            print(f"API Verification: {len(our_cards_via_api)}/10 test cards confirmed in backend")
            print()

        # ============================================================
        # PHASE 2: Selenium UI Testing (Where the Bug Happens!)
        # ============================================================

        if verbose:
            print("PHASE 2: UI Testing with Selenium")
            print("=" * 70)
            print("Now testing the React UI where the bug manifests...")
            print()

        # Launch browser
        if verbose:
            print("Step 4: Launching Chrome...")

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )
        wait = WebDriverWait(driver, 15)

        if verbose:
            print("✓ Browser launched")

        # Navigate to app
        frontend_url = "http://localhost:5173"
        driver.get(frontend_url)
        time.sleep(2)

        if verbose:
            print(f"✓ Navigated to {frontend_url}")

        # Login through UI to get session cookies
        if verbose:
            print("Step 5: Login through UI...")

        # Navigate to root (/) where AuthPage with LoginForm is
        driver.get(f"{frontend_url}/")
        time.sleep(2)  # Wait for React to render

        # Take screenshot of login page
        driver.save_screenshot("/tmp/test_hybrid_01_login_page.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_01_login_page.png")

        # Find and fill login form using correct IDs from LoginForm.jsx
        # The login tab should be active by default
        username_input = wait.until(
            EC.presence_of_element_located((By.ID, "login-username"))
        )
        username_input.clear()
        username_input.send_keys(username)

        password_input = driver.find_element(By.ID, "login-password")
        password_input.clear()
        password_input.send_keys(password)

        # Take screenshot before submitting
        driver.save_screenshot("/tmp/test_hybrid_02_login_filled.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_02_login_filled.png")

        password_input.send_keys(Keys.RETURN)

        # Wait for login to complete and navigation to /decks
        time.sleep(3)

        # Take screenshot after login
        driver.save_screenshot("/tmp/test_hybrid_03_after_login.png")

        if verbose:
            print("✓ Logged in through UI")
            print(f"  Current URL: {driver.current_url}")
            print(f"  Screenshot: /tmp/test_hybrid_03_after_login.png")

            # Verify we're actually logged in by checking URL
            if driver.current_url == f"{frontend_url}/decks":
                print("  ✓ Successfully redirected to /decks")
            else:
                print(f"  ⚠️  WARNING: Expected /decks but got {driver.current_url}")
            print()

        # Navigate to decks page (in case we're not there)
        if verbose:
            print("Step 6: Verify on Decks page...")

        if driver.current_url != f"{frontend_url}/decks":
            driver.get(f"{frontend_url}/decks")
            time.sleep(2)

        # Take screenshot of decks page
        driver.save_screenshot("/tmp/test_hybrid_04_decks_page.png")

        if verbose:
            print("✓ On Decks page")
            print(f"  Screenshot: /tmp/test_hybrid_04_decks_page.png")
            print()

        # Navigate directly to cards view using URL (Option 2: most reliable)
        if verbose:
            print("Step 7: Navigate to cards view for default deck...")

        cards_url = f"{frontend_url}/decks/{default_deck_id}/cards"
        driver.get(cards_url)
        time.sleep(3)  # Give React time to load cards

        if verbose:
            print(f"  ✓ Navigated to {cards_url}")
            print(f"  Current URL: {driver.current_url}")

        # Take screenshot of initial cards view
        driver.save_screenshot("/tmp/test_hybrid_05_initial_cards_view.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_05_initial_cards_view.png")

        # Count cards before switch
        cards_before_count = len(driver.find_elements(By.CSS_SELECTOR, "[data-card-id], .card, .flashcard, div[class*='card']"))

        if verbose:
            print(f"  Visible card elements in initial cards view: {cards_before_count}")
            print()

        # Go back to decks list using direct navigation
        if verbose:
            print("Step 8: Return to decks list...")

        driver.get(f"{frontend_url}/decks")
        time.sleep(2)

        if verbose:
            print(f"  ✓ Navigated back to /decks")
            print(f"  Current URL: {driver.current_url}")

        # Take screenshot of decks list
        driver.save_screenshot("/tmp/test_hybrid_06_back_to_decks.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_06_back_to_decks.png")
            print()

        # CREATE NEW DECK via API (faster and more reliable)
        if verbose:
            print("Step 9: Create new deck 'Hybrid Test Deck B' via API...")

        # Take screenshot before creating deck
        driver.save_screenshot("/tmp/test_hybrid_07_before_create_deck.png")

        # Create via API
        new_deck = api_client.create_deck("Hybrid Test Deck B")
        new_deck_id = new_deck['id']
        new_deck_name = new_deck['name']

        if verbose:
            print(f"✓ New deck created: {new_deck_name} (ID: {new_deck_id})")

        # Navigate to decks page to see new deck (NO refresh, just navigate)
        driver.get(f"{frontend_url}/decks")
        time.sleep(2)

        # Take screenshot after deck creation
        driver.save_screenshot("/tmp/test_hybrid_08_deck_created.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_08_deck_created.png")
            print()

        # SWITCH TO NEW DECK - Browse cards using direct URL
        if verbose:
            print("Step 10: Browse cards in 'Hybrid Test Deck B'...")

        new_deck_cards_url = f"{frontend_url}/decks/{new_deck_id}/cards"
        driver.get(new_deck_cards_url)
        time.sleep(2)

        if verbose:
            print(f"  ✓ Navigated to {new_deck_cards_url}")
            print(f"  Current URL: {driver.current_url}")

        # Take screenshot of new deck cards view (should be empty)
        driver.save_screenshot("/tmp/test_hybrid_09_new_deck_cards.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_09_new_deck_cards.png")
            print()

        # SWITCH BACK TO DEFAULT DECK (CRITICAL MOMENT!)
        if verbose:
            print("Step 11: Go back to decks list...")

        driver.get(f"{frontend_url}/decks")
        time.sleep(2)

        if verbose:
            print(f"  ✓ Navigated back to /decks")

        # Take screenshot of decks list
        driver.save_screenshot("/tmp/test_hybrid_10_back_to_decks_list.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_10_back_to_decks_list.png")
            print()

        # Browse default deck cards (CRITICAL MOMENT - will cards appear?)
        if verbose:
            print(f"Step 12: Browse cards in '{default_deck_name}' (CRITICAL!)...")

        default_deck_cards_url = f"{frontend_url}/decks/{default_deck_id}/cards"
        driver.get(default_deck_cards_url)
        time.sleep(3)  # Give UI time to update

        if verbose:
            print(f"  ✓ Navigated to {default_deck_cards_url}")
            print(f"  Current URL: {driver.current_url}")

        # Take screenshot after browsing default deck
        driver.save_screenshot("/tmp/test_hybrid_11_default_deck_cards.png")

        if verbose:
            print(f"  Screenshot: /tmp/test_hybrid_11_default_deck_cards.png")
            print()

        # COUNT VISIBLE CARDS AFTER SWITCH (THE MOMENT OF TRUTH!)
        if verbose:
            print("Step 13: Count visible cards after switch (MOMENT OF TRUTH!)...")

        time.sleep(2)  # Ensure UI has updated

        # Take final screenshot of current state
        driver.save_screenshot("/tmp/test_hybrid_12_final_cards_count.png")

        # Try to count visible card elements
        card_elements = driver.find_elements(By.CSS_SELECTOR, "[data-card-id], .card, .flashcard, div[class*='card'], li")
        cards_after_count = len(card_elements)

        # Also check via API to confirm backend still has cards
        cards_via_api_after = api_client.get_deck_cards(default_deck_id)
        our_cards_via_api_after = [c for c in cards_via_api_after if any(tc['front'] == c['front'] for tc in test_cards)]

        if verbose:
            print(f"  Visible card elements AFTER switch: {cards_after_count}")
            print(f"  Cards in backend (via API): {len(our_cards_via_api_after)}/10")
            print(f"  Screenshot: /tmp/test_hybrid_12_final_cards_count.png")
            print()

        # DETERMINE TEST RESULT
        backend_has_all_cards = len(our_cards_via_api_after) == 10

        if backend_has_all_cards and cards_after_count == 0:
            # THIS IS THE BUG!
            if verbose:
                print("=" * 70)
                print("🔴 BUG REPRODUCED!")
                print("=" * 70)
                print("Backend has all 10 cards (confirmed via API)")
                print("BUT UI shows 0 cards!")
                print()
                print("This is the 'lost cards' bug:")
                print("- Cards exist in database ✓")
                print("- API returns cards correctly ✓")
                print("- Frontend fails to display them ✗")
                print()

            result.end(
                status="FAIL",
                error_message="Cards invisible in UI after deck switch (backend has them)",
                cards_in_backend=10,
                cards_visible_in_ui=0,
                bug_type="frontend_state_management"
            )

        elif backend_has_all_cards and cards_after_count < 118:
            if verbose:
                print("=" * 70)
                print("⚠️  PARTIAL BUG?")
                print("=" * 70)
                print(f"Backend has all 10 test cards")
                print(f"UI shows {cards_after_count} elements (expected ~118)")
                print("Some cards may be missing from UI")
                print()

            result.end(
                status="FAIL",
                error_message=f"Fewer cards visible than expected: {cards_after_count} vs ~118",
                cards_in_backend=10,
                cards_visible_in_ui=cards_after_count
            )

        else:
            if verbose:
                print("=" * 70)
                print("✅ TEST PASSED")
                print("=" * 70)
                print("Cards remain visible after deck switching")
                print()

            result.end(
                status="PASS",
                cards_in_backend=10,
                cards_visible_in_ui=cards_after_count
            )

    except Exception as e:
        if verbose:
            print(f"\n❌ Test Error: {e}")
            import traceback
            traceback.print_exc()

        if driver:
            try:
                driver.save_screenshot("/tmp/test_hybrid_error.png")
                if verbose:
                    print("Screenshot saved: /tmp/test_hybrid_error.png")
            except:
                pass

        result.end(
            status="ERROR",
            error_message=str(e)
        )

    finally:
        # Cleanup
        if api_client:
            try:
                api_client.logout()
            except:
                pass

        if driver:
            driver.quit()
            if verbose:
                print("✓ Browser closed")

    return result


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Hybrid E2E Test 1.1')
    parser.add_argument('--quiet', action='store_true', help='Reduce output')
    parser.add_argument('--visible', action='store_true', help='Show browser')

    args = parser.parse_args()

    result = test_1_1_hybrid_simple_switch(
        verbose=not args.quiet,
        headless=not args.visible
    )

    if args.quiet:
        print(result.to_string(verbose=True))

    # Exit codes
    if result.status == "PASS":
        sys.exit(0)
    elif result.status == "FAIL":
        sys.exit(1)  # Bug found!
    else:
        sys.exit(2)  # Error


if __name__ == "__main__":
    main()
