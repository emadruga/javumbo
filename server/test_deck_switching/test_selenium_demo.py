#!/usr/bin/env python3
"""
Selenium Demo - Test that browser automation works

This is a simple test to verify that Selenium can:
1. Launch Chrome
2. Navigate to the React app
3. Find elements on the page
4. Take a screenshot

If this works, we can proceed with full E2E tests.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def test_selenium_demo():
    """Demo test to verify Selenium setup"""

    print("=" * 70)
    print("Selenium Setup Test")
    print("=" * 70)
    print()

    print("Step 1: Launching Chrome...")

    # Setup Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode (no GUI)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    # Initialize driver with automatic ChromeDriver management
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )

    try:
        print("✓ Chrome launched successfully")
        print()

        print("Step 2: Navigating to React app (http://localhost:5173)...")
        driver.get("http://localhost:5173")

        # Wait for page to load
        time.sleep(2)

        print(f"✓ Page loaded: {driver.title}")
        print(f"  Current URL: {driver.current_url}")
        print()

        print("Step 3: Looking for elements...")

        # Try to find the login link or form
        try:
            # Wait up to 10 seconds for an element to appear
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print("✓ Found body element")

            # Get page source snippet
            page_source = driver.page_source[:500]
            print(f"  Page source preview: {page_source}...")

        except Exception as e:
            print(f"⚠️  Could not find expected elements: {e}")

        print()
        print("Step 4: Taking screenshot...")

        screenshot_path = "/tmp/selenium_test.png"
        driver.save_screenshot(screenshot_path)
        print(f"✓ Screenshot saved to: {screenshot_path}")
        print()

        print("=" * 70)
        print("✅ Selenium Setup Test PASSED!")
        print("=" * 70)
        print("Chrome automation is working correctly.")
        print("Ready to implement full E2E tests.")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        raise

    finally:
        print("Closing browser...")
        driver.quit()
        print("✓ Browser closed")


if __name__ == "__main__":
    test_selenium_demo()
