"""
Test Deck Switching Package

This package provides automated testing infrastructure for the "lost cards" bug
identified in the JAVUMBO flashcard application. It contains tools to reproduce
and verify the deck switching issues documented in:
- docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md
- docs/LOST_CARDS_INVESTIGATION_SUMMARY.md
- docs/LOST_CARDS_REPRODUCTION_PLAN.md

The package includes:
- base_test_client: Reusable test client that mimics frontend behavior
- config: Configuration management for different test environments
- utils: Helper utilities for assertions, reporting, and database verification

Test suites are organized following the structure in the comparative analysis:
- Test Suite 1: Basic Deck Switching (test_1_1, test_1_2)
- Test Suite 2: Rapid/Multiple Switching (Rayssa pattern, Gabrielle pattern)
- ... (additional suites as documented)

Usage:
    from test_deck_switching import TestClient, get_config, TestResult

    config = get_config()
    client = TestClient(config.base_url, "testuser", "password")
    client.login()

    # Run tests...

For running complete test suites:
    python run_suite_1.py --env local
    python run_suite_1.py --env staging --verbose

Package Version: 1.0.0
Created: November 2025
Purpose: Reproduce and validate fix for lost cards bug
"""

__version__ = "1.0.0"
__author__ = "JAVUMBO Development Team"
__doc__ = __doc__

# Import main classes and functions for convenient access
from .base_test_client import TestClient, APICallError, register_test_user
from .config import (
    TestConfig,
    TestEnvironment,
    get_config,
    get_config_from_args,
    generate_test_username,
    get_test_user_db_path
)
from .utils import (
    TestResult,
    format_test_header,
    format_section,
    format_summary,
    assert_card_count,
    assert_cards_exist,
    assert_deck_exists,
    verify_cards_in_database,
    verify_deck_in_database,
    save_test_results_json,
    save_test_results_markdown,
    Timer
)

__all__ = [
    # Client
    'TestClient',
    'APICallError',
    'register_test_user',

    # Config
    'TestConfig',
    'TestEnvironment',
    'get_config',
    'get_config_from_args',
    'generate_test_username',
    'get_test_user_db_path',

    # Utils
    'TestResult',
    'format_test_header',
    'format_section',
    'format_summary',
    'assert_card_count',
    'assert_cards_exist',
    'assert_deck_exists',
    'verify_cards_in_database',
    'verify_deck_in_database',
    'save_test_results_json',
    'save_test_results_markdown',
    'Timer',
]
