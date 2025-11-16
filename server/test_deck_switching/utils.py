#!/usr/bin/env python3
"""
Utility Functions for Deck Switching Tests

This module provides helper functions for:
- Test result tracking and reporting
- Database verification (for local tests)
- Assertion helpers with detailed error messages
- Test timing and performance measurement
- Log formatting and output

Usage:
    from utils import TestResult, assert_card_count, format_test_header

    result = TestResult("test_1_1")
    result.start()

    # ... run test ...

    result.end(status="PASS", cards_expected=10, cards_found=10)
    print(result.to_string())
"""

import time
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ==================== Color Output for Terminal ====================

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def disable():
        """Disable colors (for file output or CI)"""
        Colors.HEADER = ''
        Colors.OKBLUE = ''
        Colors.OKCYAN = ''
        Colors.OKGREEN = ''
        Colors.WARNING = ''
        Colors.FAIL = ''
        Colors.ENDC = ''
        Colors.BOLD = ''
        Colors.UNDERLINE = ''


def colored(text: str, color: str) -> str:
    """Wrap text with color code"""
    return f"{color}{text}{Colors.ENDC}"


# ==================== Test Result Tracking ====================

@dataclass
class TestResult:
    """
    Track the result of a single test execution.

    This class captures all relevant information about a test run,
    including timing, status, and detailed results.

    Attributes:
        test_id: Unique identifier for the test (e.g., "1.1")
        test_name: Descriptive name of the test
        status: Test status (PASS, FAIL, ERROR, SKIP)
        start_time: When the test started
        end_time: When the test ended
        duration_ms: Test duration in milliseconds
        error_message: Error message if test failed
        details: Additional test-specific details
        assertions: List of assertion results
    """
    test_id: str
    test_name: str = ""
    status: str = "PENDING"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    assertions: List[Dict[str, Any]] = field(default_factory=list)

    def start(self) -> None:
        """Mark the start of the test"""
        self.start_time = time.time()
        self.status = "RUNNING"

    def end(self, status: str = "PASS", error_message: Optional[str] = None, **details) -> None:
        """
        Mark the end of the test.

        Args:
            status: Final test status (PASS, FAIL, ERROR, SKIP)
            error_message: Error message if test failed
            **details: Additional details to store (e.g., cards_expected=10)
        """
        self.end_time = time.time()
        self.status = status
        self.error_message = error_message

        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time) * 1000

        # Store additional details
        for key, value in details.items():
            self.details[key] = value

    def add_assertion(self, description: str, passed: bool, expected: Any, actual: Any) -> None:
        """
        Record an assertion result.

        Args:
            description: Description of what was asserted
            passed: Whether the assertion passed
            expected: Expected value
            actual: Actual value
        """
        self.assertions.append({
            "description": description,
            "passed": passed,
            "expected": expected,
            "actual": actual
        })

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "details": self.details,
            "assertions": self.assertions,
            "timestamp": datetime.now().isoformat()
        }

    def to_string(self, verbose: bool = True) -> str:
        """
        Format test result as a string.

        Args:
            verbose: Include detailed assertion information

        Returns:
            Formatted string representation
        """
        # Status icon and color
        if self.status == "PASS":
            icon = "✓"
            color = Colors.OKGREEN
        elif self.status == "FAIL":
            icon = "✗"
            color = Colors.FAIL
        elif self.status == "ERROR":
            icon = "⚠"
            color = Colors.WARNING
        else:
            icon = "○"
            color = Colors.OKCYAN

        # Header line
        result = colored(f"{icon} Test {self.test_id}: {self.test_name or 'Unnamed'}", color)
        result += f" ({self.duration_ms:.0f}ms)\n"

        # Status and basic info
        result += f"  Status: {colored(self.status, color)}\n"

        # Error message if present
        if self.error_message:
            result += colored(f"  Error: {self.error_message}\n", Colors.FAIL)

        # Details
        if self.details:
            result += "  Details:\n"
            for key, value in self.details.items():
                result += f"    {key}: {value}\n"

        # Assertions (if verbose)
        if verbose and self.assertions:
            result += "  Assertions:\n"
            for assertion in self.assertions:
                icon = "✓" if assertion["passed"] else "✗"
                color = Colors.OKGREEN if assertion["passed"] else Colors.FAIL
                result += colored(f"    {icon} {assertion['description']}\n", color)
                if not assertion["passed"]:
                    result += f"      Expected: {assertion['expected']}\n"
                    result += f"      Actual: {assertion['actual']}\n"

        return result


# ==================== Formatting Helpers ====================

def format_test_header(test_id: str, test_name: str) -> str:
    """
    Format a test header for console output.

    Args:
        test_id: Test ID (e.g., "1.1")
        test_name: Test name

    Returns:
        Formatted header string
    """
    header = f"\n{'='*70}\n"
    header += colored(f"Test {test_id}: {test_name}", Colors.BOLD)
    header += f"\n{'='*70}\n"
    return header


def format_section(title: str) -> str:
    """Format a section divider"""
    return f"\n{'-'*70}\n{title}\n{'-'*70}\n"


def format_summary(results: List[TestResult]) -> str:
    """
    Format a summary of multiple test results.

    Args:
        results: List of TestResult objects

    Returns:
        Formatted summary string
    """
    if not results:
        return "No test results to summarize."

    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status == "SKIP")

    total_time = sum(r.duration_ms for r in results)

    summary = f"\n{'='*70}\n"
    summary += colored("TEST SUITE SUMMARY", Colors.BOLD)
    summary += f"\n{'='*70}\n"
    summary += f"Total Tests: {total}\n"
    summary += colored(f"Passed: {passed}\n", Colors.OKGREEN)
    if failed > 0:
        summary += colored(f"Failed: {failed}\n", Colors.FAIL)
    if errors > 0:
        summary += colored(f"Errors: {errors}\n", Colors.WARNING)
    if skipped > 0:
        summary += f"Skipped: {skipped}\n"
    summary += f"Total Time: {total_time:.0f}ms ({total_time/1000:.2f}s)\n"

    # Pass rate
    if total > 0:
        pass_rate = (passed / total) * 100
        if pass_rate == 100:
            color = Colors.OKGREEN
        elif pass_rate >= 80:
            color = Colors.WARNING
        else:
            color = Colors.FAIL
        summary += colored(f"Pass Rate: {pass_rate:.1f}%\n", color)

    return summary


# ==================== Assertion Helpers ====================

def assert_card_count(
    actual_count: int,
    expected_count: int,
    result: Optional[TestResult] = None
) -> bool:
    """
    Assert that card count matches expectation.

    Args:
        actual_count: Actual number of cards
        expected_count: Expected number of cards
        result: TestResult object to record assertion (optional)

    Returns:
        True if counts match, False otherwise
    """
    passed = actual_count == expected_count

    if result:
        result.add_assertion(
            description=f"Card count should be {expected_count}",
            passed=passed,
            expected=expected_count,
            actual=actual_count
        )

    return passed


def assert_cards_exist(
    cards: List[Dict],
    expected_fronts: List[str],
    result: Optional[TestResult] = None
) -> bool:
    """
    Assert that specific cards exist in the list.

    Args:
        cards: List of card dictionaries from API
        expected_fronts: List of expected front texts
        result: TestResult object to record assertions (optional)

    Returns:
        True if all expected cards found, False otherwise
    """
    card_fronts = [card.get('front') for card in cards]
    all_found = True

    for expected_front in expected_fronts:
        found = expected_front in card_fronts

        if result:
            result.add_assertion(
                description=f"Card '{expected_front[:30]}...' should exist",
                passed=found,
                expected="Present",
                actual="Present" if found else "Missing"
            )

        if not found:
            all_found = False

    return all_found


def assert_deck_exists(
    decks: List[Dict],
    deck_name: str,
    result: Optional[TestResult] = None
) -> bool:
    """
    Assert that a deck with the given name exists.

    Args:
        decks: List of deck dictionaries from API
        deck_name: Expected deck name
        result: TestResult object to record assertion (optional)

    Returns:
        True if deck found, False otherwise
    """
    deck_names = [deck.get('name') for deck in decks]
    found = deck_name in deck_names

    if result:
        result.add_assertion(
            description=f"Deck '{deck_name}' should exist",
            passed=found,
            expected="Present",
            actual="Present" if found else "Missing"
        )

    return found


# ==================== Database Verification (for local tests) ====================

def verify_cards_in_database(
    db_path: str,
    deck_id: int,
    expected_count: Optional[int] = None
) -> Dict[str, Any]:
    """
    Directly query the SQLite database to verify card count.

    This is used for local tests to confirm backend data integrity
    when frontend might not be showing cards correctly.

    Args:
        db_path: Path to the user's SQLite database
        deck_id: Deck ID to check
        expected_count: Expected count (optional, for comparison)

    Returns:
        Dictionary with verification results

    Example:
        >>> result = verify_cards_in_database("user_123.db", 1, expected_count=10)
        >>> print(f"Found {result['actual_count']} cards")
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count cards in the deck
        cursor.execute("""
            SELECT COUNT(*) FROM cards WHERE did = ?
        """, (deck_id,))

        actual_count = cursor.fetchone()[0]

        # Get card details if count is small
        cards = []
        if actual_count <= 20:
            cursor.execute("""
                SELECT c.id, n.flds, c.queue, c.type
                FROM cards c
                JOIN notes n ON c.nid = n.id
                WHERE c.did = ?
                ORDER BY c.id
            """, (deck_id,))

            for row in cursor.fetchall():
                card_id, fields, queue, card_type = row
                # Parse fields (format is "front\x1fback")
                parts = fields.split('\x1f')
                cards.append({
                    "id": card_id,
                    "front": parts[0] if len(parts) > 0 else "",
                    "back": parts[1] if len(parts) > 1 else "",
                    "queue": queue,
                    "type": card_type
                })

        conn.close()

        matches = actual_count == expected_count if expected_count is not None else None

        return {
            "success": True,
            "actual_count": actual_count,
            "expected_count": expected_count,
            "matches": matches,
            "cards": cards
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": str(e),
            "actual_count": 0,
            "expected_count": expected_count,
            "matches": False
        }


def verify_deck_in_database(db_path: str, deck_id: int) -> Dict[str, Any]:
    """
    Verify a deck exists in the database.

    Args:
        db_path: Path to the user's SQLite database
        deck_id: Deck ID to check

    Returns:
        Dictionary with deck information
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get deck info from col table
        cursor.execute("SELECT decks FROM col")
        decks_json = cursor.fetchone()[0]
        decks = json.loads(decks_json)

        conn.close()

        deck_info = decks.get(str(deck_id))

        return {
            "success": True,
            "exists": deck_info is not None,
            "deck_info": deck_info
        }

    except (sqlite3.Error, json.JSONDecodeError) as e:
        return {
            "success": False,
            "error": str(e),
            "exists": False
        }


# ==================== Report Generation ====================

def save_test_results_json(results: List[TestResult], filepath: str) -> None:
    """
    Save test results to a JSON file.

    Args:
        results: List of TestResult objects
        filepath: Path to save JSON file
    """
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "results": [r.to_dict() for r in results]
    }

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Results saved to: {filepath}")


def save_test_results_markdown(results: List[TestResult], filepath: str) -> None:
    """
    Save test results to a Markdown file.

    Args:
        results: List of TestResult objects
        filepath: Path to save Markdown file
    """
    md = f"# Test Suite Results\n\n"
    md += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")

    md += f"## Summary\n\n"
    md += f"- **Total Tests**: {total}\n"
    md += f"- **Passed**: {passed}\n"
    md += f"- **Failed**: {failed}\n"
    md += f"- **Pass Rate**: {(passed/total*100):.1f}%\n\n"

    # Individual results
    md += f"## Test Results\n\n"

    for result in results:
        icon = "✅" if result.status == "PASS" else "❌"
        md += f"### {icon} Test {result.test_id}: {result.test_name}\n\n"
        md += f"- **Status**: {result.status}\n"
        md += f"- **Duration**: {result.duration_ms:.0f}ms\n"

        if result.error_message:
            md += f"- **Error**: {result.error_message}\n"

        if result.details:
            md += f"- **Details**:\n"
            for key, value in result.details.items():
                md += f"  - {key}: {value}\n"

        if result.assertions:
            md += f"- **Assertions**:\n"
            for assertion in result.assertions:
                icon = "✓" if assertion["passed"] else "✗"
                md += f"  - {icon} {assertion['description']}\n"
                if not assertion["passed"]:
                    md += f"    - Expected: {assertion['expected']}\n"
                    md += f"    - Actual: {assertion['actual']}\n"

        md += "\n"

    with open(filepath, 'w') as f:
        f.write(md)

    print(f"Markdown report saved to: {filepath}")


# ==================== Timing Utilities ====================

class Timer:
    """Simple timer for measuring test duration"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start the timer"""
        self.start_time = time.time()

    def stop(self) -> float:
        """
        Stop the timer.

        Returns:
            Duration in seconds
        """
        self.end_time = time.time()
        return self.elapsed()

    def elapsed(self) -> float:
        """
        Get elapsed time in seconds.

        Returns:
            Elapsed time (or 0 if not started)
        """
        if self.start_time is None:
            return 0.0

        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        return self.elapsed() * 1000


if __name__ == "__main__":
    """
    Demo the utilities module.
    """
    print("=" * 70)
    print("Utilities Module Demo")
    print("=" * 70)

    # Test result tracking demo
    print("\n" + format_section("Test Result Tracking"))

    result1 = TestResult("1.1", "Simple Switch and Return")
    result1.start()
    time.sleep(0.1)  # Simulate test execution
    result1.add_assertion("Card count matches", True, 10, 10)
    result1.end(status="PASS", cards_expected=10, cards_found=10)

    print(result1.to_string())

    result2 = TestResult("1.2", "Add Card After Switch")
    result2.start()
    time.sleep(0.05)
    result2.add_assertion("Card count matches", False, 6, 1)
    result2.end(status="FAIL", error_message="BUG DETECTED: Only 1 card visible after switch",
                cards_expected=6, cards_found=1)

    print(result2.to_string())

    # Summary demo
    results = [result1, result2]
    print(format_summary(results))

    # Assertion helpers demo
    print("\n" + format_section("Assertion Helpers"))

    cards = [
        {"cardId": 1, "front": "Question 1", "back": "Answer 1"},
        {"cardId": 2, "front": "Question 2", "back": "Answer 2"},
    ]

    result3 = TestResult("demo", "Assertion Demo")
    assert_card_count(len(cards), 2, result3)
    assert_cards_exist(cards, ["Question 1", "Question 3"], result3)

    print(result3.to_string())

    # Timer demo
    print("\n" + format_section("Timer Demo"))

    timer = Timer()
    timer.start()
    time.sleep(0.2)
    duration = timer.stop()

    print(f"Operation took {duration*1000:.0f}ms")

    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)
