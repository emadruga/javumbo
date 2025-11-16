#!/usr/bin/env python3
"""
E2E Test 1.1: Simple Switch and Return (Frontend UI Test)

This test reproduces the "lost cards" bug by interacting with the actual React UI
using Selenium browser automation.

Unlike the API test, this test:
- Clicks buttons in the browser
- Fills out forms
- Navigates through the UI
- Checks what the USER SEES (not just what the API returns)

This should reproduce the bug where cards become invisible in the UI after deck switching.

Reference: docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md - Test Suite 1, Test 1.1
"""

import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from test_deck_switching import (
    TestResult,
    generate_test_username,
    format_test_header,
    get_config
)


class FrontendTestClient:
    """
    Selenium-based frontend test client for E2E testing.

    This client interacts with the actual React UI to reproduce bugs
    that only occur in frontend state management.
    """

    def __init__(self, frontend_url="http://localhost:5173", headless=True, verbose=True):
        self.frontend_url = frontend_url
        self.headless = headless
        self.verbose = verbose
        self.driver = None
        self.wait = None

    def start_browser(self):
        """Launch Chrome browser"""
        if self.verbose:
            print("Launching Chrome browser...")

        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')

        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )
        self.wait = WebDriverWait(self.driver, 10)

        if self.verbose:
            print("✓ Browser launched")

    def close_browser(self):
        """Close Chrome browser"""
        if self.driver:
            self.driver.quit()
            if self.verbose:
                print("✓ Browser closed")

    def navigate_to(self, path="/"):
        """Navigate to a specific path in the app"""
        url = f"{self.frontend_url}{path}"
        if self.verbose:
            print(f"Navigating to: {url}")
        self.driver.get(url)
        time.sleep(1)  # Let page load

    def register_user(self, username, name, password):
        """Register a new user through the UI"""
        if self.verbose:
            print(f"Registering user: {username}")

        # Navigate to registration page
        self.navigate_to("/register")

        # Fill out registration form
        username_input = self.wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.clear()
        username_input.send_keys(username)

        name_input = self.driver.find_element(By.NAME, "name")
        name_input.clear()
        name_input.send_keys(name)

        password_input = self.driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(password)

        # Submit form
        submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        # Wait for redirect to login or home
        time.sleep(2)

        if self.verbose:
            print(f"✓ User registered")

    def login_user(self, username, password):
        """Login through the UI"""
        if self.verbose:
            print(f"Logging in as: {username}")

        # Navigate to login page
        self.navigate_to("/login")

        # Fill out login form
        username_input = self.wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.clear()
        username_input.send_keys(username)

        password_input = self.driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(password)

        # Submit form
        submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        # Wait for redirect to home/decks
        time.sleep(2)

        if self.verbose:
            print(f"✓ Logged in successfully")

    def create_deck(self, deck_name):
        """Create a new deck through the UI"""
        if self.verbose:
            print(f"Creating deck: {deck_name}")

        # Navigate to decks page
        self.navigate_to("/decks")
        time.sleep(1)

        # Click "Create Deck" button
        try:
            create_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Create') or contains(text(), 'Add') or contains(text(), 'New')]"))
            )
            create_button.click()
            time.sleep(1)

            # Fill in deck name
            name_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[name='deckName'], input[placeholder*='name']"))
            )
            name_input.clear()
            name_input.send_keys(deck_name)

            # Submit
            submit = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit.click()
            time.sleep(1)

            if self.verbose:
                print(f"✓ Deck '{deck_name}' created")

        except TimeoutException:
            if self.verbose:
                print(f"⚠️  Could not find create deck button - trying alternative...")
            # Alternative: might already have a form visible

    def add_card_to_current_deck(self, front, back):
        """Add a card through the UI"""
        # Navigate to add card page
        self.navigate_to("/add")
        time.sleep(1)

        # Fill out card form
        front_input = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='front'], textarea[placeholder*='front'], input[name='front']"))
        )
        front_input.clear()
        front_input.send_keys(front)

        back_input = self.driver.find_element(By.CSS_SELECTOR, "textarea[name='back'], textarea[placeholder*='back'], input[name='back']")
        back_input.clear()
        back_input.send_keys(back)

        # Submit
        submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        time.sleep(1.5)  # Card creation delay

    def switch_to_deck(self, deck_name):
        """Switch to a specific deck through the UI"""
        if self.verbose:
            print(f"Switching to deck: {deck_name}")

        # Navigate to decks page
        self.navigate_to("/decks")
        time.sleep(1)

        # Find and click on the deck
        try:
            deck_element = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//div[contains(text(), '{deck_name}')] | //h3[contains(text(), '{deck_name}')] | //span[contains(text(), '{deck_name}')]"))
            )
            deck_element.click()
            time.sleep(1)

            if self.verbose:
                print(f"✓ Switched to deck: {deck_name}")

        except TimeoutException:
            if self.verbose:
                print(f"⚠️  Could not find deck: {deck_name}")
            raise

    def count_visible_cards_in_deck(self, deck_name):
        """
        Count how many cards are VISIBLE in the UI for a specific deck.
        This is THE CRITICAL CHECK - it looks at what the user sees, not what the API returns.
        """
        if self.verbose:
            print(f"Counting visible cards in deck: {deck_name}")

        # Navigate to decks page
        self.navigate_to("/decks")
        time.sleep(1)

        # Click on deck to view cards
        try:
            deck_element = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//div[contains(text(), '{deck_name}')] | //h3[contains(text(), '{deck_name}')] | //span[contains(text(), '{deck_name}')]"))
            )

            # Look for card count in the deck display
            # This varies by UI design - might be in a badge, span, etc.
            try:
                parent = deck_element.find_element(By.XPATH, "./..")
                card_count_text = parent.text

                if self.verbose:
                    print(f"Deck display text: {card_count_text}")

            except:
                pass

            # Click to view cards
            deck_element.click()
            time.sleep(2)

            # Count card elements in the DOM
            # Looking for common card selectors
            card_selectors = [
                ".card",
                ".flashcard",
                "[data-card-id]",
                ".card-item",
                "div[class*='card']"
            ]

            total_cards = 0
            for selector in card_selectors:
                try:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if cards:
                        total_cards = len(cards)
                        if self.verbose:
                            print(f"Found {total_cards} cards using selector: {selector}")
                        break
                except:
                    continue

            if self.verbose:
                print(f"✓ Visible cards in deck: {total_cards}")

            return total_cards

        except TimeoutException:
            if self.verbose:
                print(f"⚠️  Could not find deck: {deck_name}")
            return 0

    def take_screenshot(self, filename):
        """Take a screenshot for debugging"""
        self.driver.save_screenshot(filename)
        if self.verbose:
            print(f"Screenshot saved: {filename}")


def test_1_1_e2e_simple_switch(verbose=True):
    """
    E2E Test 1.1: Simple Switch and Return (Frontend)

    This test reproduces the bug by interacting with the React UI.
    """
    result = TestResult("1.1-E2E", "Simple Switch and Return (Frontend E2E)")

    if verbose:
        print(format_test_header("1.1-E2E", "Simple Switch and Return (Frontend E2E)"))
        print("Testing: React UI deck switching")
        print("Method: Selenium browser automation")
        print()

    result.start()

    # Initialize frontend client
    client = FrontendTestClient(verbose=verbose)

    try:
        # Generate test user
        username = generate_test_username()
        password = "test_password_123"
        name = "E2E Test User"

        if verbose:
            print(f"Test User: {username}")
            print()

        # Start browser
        client.start_browser()

        # Register and login
        if verbose:
            print("STEP 1: Register and Login")
            print("-" * 70)

        client.register_user(username, name, password)
        client.login_user(username, password)

        if verbose:
            print()
            print("STEP 2: Create 10 Cards in Default Deck")
            print("-" * 70)

        # Wait for sample cards to be created
        time.sleep(2)

        # Add 10 test cards
        for i in range(1, 11):
            front = f"E2E Test Card {i}"
            back = f"E2E Answer {i}"
            client.add_card_to_current_deck(front, back)

            if verbose and i % 3 == 0:
                print(f"  Created {i}/10 cards...")

        if verbose:
            print("✓ All 10 cards created")
            print()

        # Take screenshot before switch
        client.take_screenshot("/tmp/test_1_1_before_switch.png")

        if verbose:
            print("STEP 3: Create New Deck 'E2E Test Deck B'")
            print("-" * 70)

        client.create_deck("E2E Test Deck B")

        if verbose:
            print()
            print("STEP 4: Switch to 'E2E Test Deck B'")
            print("-" * 70)

        client.switch_to_deck("E2E Test Deck B")

        if verbose:
            print()
            print("STEP 5: Switch Back to Default Deck")
            print("-" * 70)

        client.switch_to_deck("Verbal Tenses")

        # Take screenshot after switch
        client.take_screenshot("/tmp/test_1_1_after_switch.png")

        if verbose:
            print()
            print("STEP 6: CRITICAL - Count Visible Cards")
            print("-" * 70)

        visible_cards = client.count_visible_cards_in_deck("Verbal Tenses")

        # Note: This will include sample cards, so we expect more than 10
        # But the key is: are our 10 test cards visible?

        if verbose:
            print(f"Total visible cards: {visible_cards}")
            print(f"Expected: At least 118 (108 sample + 10 test cards)")
            print()

        # Determine result
        if visible_cards >= 118:
            if verbose:
                print("=" * 70)
                print("✅ TEST PASSED")
                print("=" * 70)
                print("All cards remain visible in the UI after deck switching")
                print()

            result.end(
                status="PASS",
                visible_cards=visible_cards,
                expected_minimum=118
            )
        elif visible_cards >= 108 and visible_cards < 118:
            if verbose:
                print("=" * 70)
                print("🔴 BUG DETECTED!")
                print("=" * 70)
                print(f"Some test cards missing from UI!")
                print(f"Visible: {visible_cards} cards")
                print(f"Expected: At least 118 cards")
                print(f"Missing: ~{118 - visible_cards} cards")
                print()
                print("This confirms the 'lost cards' bug!")
                print("Cards exist in backend but are invisible in UI")
                print()

            result.end(
                status="FAIL",
                error_message=f"Cards missing from UI: expected >=118, found {visible_cards}",
                visible_cards=visible_cards,
                expected_minimum=118,
                cards_lost=118 - visible_cards
            )
        else:
            if verbose:
                print("=" * 70)
                print("⚠️  UNEXPECTED RESULT")
                print("=" * 70)
                print(f"Visible cards: {visible_cards}")
                print("This might indicate a counting error or UI change")
                print()

            result.end(
                status="ERROR",
                error_message=f"Unexpected card count: {visible_cards}",
                visible_cards=visible_cards
            )

    except Exception as e:
        if verbose:
            print(f"\n❌ Test Error: {e}")
            import traceback
            traceback.print_exc()

        # Take error screenshot
        try:
            client.take_screenshot("/tmp/test_1_1_error.png")
        except:
            pass

        result.end(
            status="ERROR",
            error_message=str(e)
        )

    finally:
        client.close_browser()

    return result


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='E2E Test 1.1: Simple Switch and Return')
    parser.add_argument('--quiet', action='store_true', help='Reduce output verbosity')
    parser.add_argument('--visible', action='store_true', help='Show browser (not headless)')

    args = parser.parse_args()

    verbose = not args.quiet

    # Override headless mode if --visible specified
    if args.visible:
        # TODO: Pass this to test function
        pass

    result = test_1_1_e2e_simple_switch(verbose=verbose)

    if not verbose:
        print(result.to_string(verbose=True))

    # Exit codes
    if result.status == "PASS":
        sys.exit(0)
    elif result.status == "FAIL":
        sys.exit(1)  # Bug detected!
    else:
        sys.exit(2)  # Error


if __name__ == "__main__":
    main()
