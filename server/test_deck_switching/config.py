#!/usr/bin/env python3
"""
Configuration Management for Deck Switching Tests

This module manages test configuration for different environments (local, staging, production).
It provides a centralized way to configure:
- API endpoints
- Database paths (for local testing)
- Test user credentials
- Test execution parameters

Usage:
    from config import get_config, TestEnvironment

    # Get configuration for local testing
    config = get_config(TestEnvironment.LOCAL)
    print(config.base_url)  # "http://localhost:5000"

    # Get configuration from environment variable
    config = get_config()  # Reads TEST_ENV environment variable

    # Override configuration
    config = get_config(TestEnvironment.STAGING, base_url="http://custom-url.com")
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TestEnvironment(Enum):
    """Enumeration of available test environments"""
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
    CUSTOM = "custom"


@dataclass
class TestConfig:
    """
    Configuration for test execution.

    Attributes:
        environment: The test environment (local, staging, production)
        base_url: Base URL of the API server
        admin_db_path: Path to admin database (None for remote servers)
        user_db_dir: Directory containing user databases (None for remote servers)
        default_password: Default password for test users
        test_user_prefix: Prefix for test usernames
        card_creation_delay: Delay between card creations (seconds)
        verbose: Enable verbose logging
        timeout: Default timeout for API calls (seconds)
    """
    environment: TestEnvironment
    base_url: str
    admin_db_path: Optional[str]
    user_db_dir: Optional[str]
    default_password: str
    test_user_prefix: str
    card_creation_delay: float
    verbose: bool
    timeout: int

    def __str__(self) -> str:
        """String representation of configuration"""
        return f"""
TestConfig:
  Environment: {self.environment.value}
  Base URL: {self.base_url}
  Admin DB: {self.admin_db_path or 'N/A (remote)'}
  User DB Dir: {self.user_db_dir or 'N/A (remote)'}
  Test User Prefix: {self.test_user_prefix}
  Verbose: {self.verbose}
"""

    def has_local_db_access(self) -> bool:
        """Check if we have local database access (for direct verification)"""
        return self.admin_db_path is not None and self.user_db_dir is not None


# Predefined configurations for different environments
DEFAULT_CONFIGS = {
    TestEnvironment.LOCAL: TestConfig(
        environment=TestEnvironment.LOCAL,
        base_url="http://localhost:8000",
        admin_db_path="../admin.db",  # Relative to test_deck_switching/
        user_db_dir="../user_dbs",
        default_password="test_password_123",
        test_user_prefix="test_deck_switching_",
        card_creation_delay=1.5,  # 1.5 seconds to avoid timestamp collisions
        verbose=True,
        timeout=10
    ),

    TestEnvironment.STAGING: TestConfig(
        environment=TestEnvironment.STAGING,
        base_url="http://54.226.152.231",
        admin_db_path=None,  # No local DB access for remote server
        user_db_dir=None,
        default_password="password123test",
        test_user_prefix="test_deck_switching_",
        card_creation_delay=0.1,
        verbose=True,
        timeout=15  # Longer timeout for remote server
    ),

    TestEnvironment.PRODUCTION: TestConfig(
        environment=TestEnvironment.PRODUCTION,
        base_url="https://flashcards.example.com",  # Replace with actual production URL
        admin_db_path=None,
        user_db_dir=None,
        default_password="secure_password_change_me",
        test_user_prefix="test_deck_switching_",
        card_creation_delay=0.2,  # Slower for production
        verbose=False,  # Less verbose in production
        timeout=20
    ),
}


def get_config(
    environment: Optional[TestEnvironment] = None,
    base_url: Optional[str] = None,
    verbose: Optional[bool] = None
) -> TestConfig:
    """
    Get test configuration for the specified environment.

    This function loads the appropriate configuration and allows overriding
    specific values. If no environment is specified, it tries to read from
    the TEST_ENV environment variable, defaulting to LOCAL.

    Args:
        environment: The test environment (if None, reads from TEST_ENV env var)
        base_url: Override the base URL (optional)
        verbose: Override verbose logging (optional)

    Returns:
        TestConfig object with the configuration

    Examples:
        >>> config = get_config()  # Uses TEST_ENV or defaults to LOCAL
        >>> config = get_config(TestEnvironment.STAGING)
        >>> config = get_config(TestEnvironment.LOCAL, base_url="http://192.168.1.100:5000")
    """
    # Determine environment
    if environment is None:
        env_str = os.environ.get("TEST_ENV", "local").lower()
        try:
            environment = TestEnvironment(env_str)
        except ValueError:
            print(f"Warning: Unknown TEST_ENV '{env_str}', defaulting to LOCAL")
            environment = TestEnvironment.LOCAL

    # Get base configuration
    if environment in DEFAULT_CONFIGS:
        config = DEFAULT_CONFIGS[environment]
    else:
        # Custom environment, use LOCAL as template
        config = DEFAULT_CONFIGS[TestEnvironment.LOCAL]

    # Apply overrides if provided
    if base_url is not None:
        config = TestConfig(
            environment=config.environment,
            base_url=base_url,
            admin_db_path=config.admin_db_path,
            user_db_dir=config.user_db_dir,
            default_password=config.default_password,
            test_user_prefix=config.test_user_prefix,
            card_creation_delay=config.card_creation_delay,
            verbose=config.verbose if verbose is None else verbose,
            timeout=config.timeout
        )

    if verbose is not None:
        config.verbose = verbose

    return config


def get_config_from_args(args) -> TestConfig:
    """
    Get configuration from command-line arguments.

    This is a helper function for CLI tools that use argparse.

    Args:
        args: argparse.Namespace object with parsed arguments

    Returns:
        TestConfig object

    Expected args attributes:
        - env: Environment name (local/staging/production)
        - base_url: Optional base URL override
        - verbose: Optional verbose flag
    """
    env = None
    if hasattr(args, 'env') and args.env:
        try:
            env = TestEnvironment(args.env.lower())
        except ValueError:
            print(f"Warning: Unknown environment '{args.env}', using LOCAL")
            env = TestEnvironment.LOCAL

    base_url = getattr(args, 'base_url', None)
    verbose = getattr(args, 'verbose', None)

    return get_config(environment=env, base_url=base_url, verbose=verbose)


# Test user generation helpers

def generate_test_username(prefix: Optional[str] = None, timestamp: bool = True) -> str:
    """
    Generate a unique test username.

    Args:
        prefix: Username prefix (uses config default if None)
        timestamp: Include timestamp for uniqueness (default: True)

    Returns:
        Generated username string (max 10 chars for API compatibility)

    Examples:
        >>> generate_test_username()
        'test1234'
        >>> generate_test_username(prefix="mytest_", timestamp=False)
        'mytest_user'
    """
    import time

    if prefix is None:
        # Use short prefix for API constraint (max 10 chars)
        prefix = "test"

    if timestamp:
        # Use only last 4-6 digits of timestamp to keep it short
        timestamp_suffix = int(time.time()) % 10000
        username = f"{prefix}{timestamp_suffix}"
        # Ensure it fits in 10 chars
        return username[:10]
    else:
        return f"{prefix}user"[:10]


def get_test_user_db_path(user_id: int, config: Optional[TestConfig] = None) -> Optional[str]:
    """
    Get the database path for a test user.

    This only works for local testing where we have filesystem access.

    Args:
        user_id: The user ID
        config: Test configuration (gets default if None)

    Returns:
        Path to user database, or None if not accessible

    Examples:
        >>> get_test_user_db_path(123)
        '../test_user_dbs/user_123.db'
    """
    if config is None:
        config = get_config()

    if config.user_db_dir is None:
        return None

    return os.path.join(config.user_db_dir, f"user_{user_id}.db")


# Environment detection helpers

def is_local_environment(config: Optional[TestConfig] = None) -> bool:
    """Check if we're running in local environment"""
    if config is None:
        config = get_config()
    return config.environment == TestEnvironment.LOCAL


def is_remote_environment(config: Optional[TestConfig] = None) -> bool:
    """Check if we're running against a remote server"""
    if config is None:
        config = get_config()
    return config.environment in [TestEnvironment.STAGING, TestEnvironment.PRODUCTION]


if __name__ == "__main__":
    """
    Demo/test the configuration module.
    """
    print("=" * 70)
    print("Configuration Module Demo")
    print("=" * 70)

    # Show all predefined configurations
    print("\nPredefined Configurations:")
    print("-" * 70)

    for env in [TestEnvironment.LOCAL, TestEnvironment.STAGING, TestEnvironment.PRODUCTION]:
        config = get_config(env)
        print(config)

    # Show environment variable usage
    print("\nEnvironment Variable Demo:")
    print("-" * 70)
    print(f"Current TEST_ENV: {os.environ.get('TEST_ENV', 'not set')}")

    config = get_config()
    print(f"Active configuration: {config.environment.value}")
    print(f"Base URL: {config.base_url}")

    # Show override demo
    print("\nOverride Demo:")
    print("-" * 70)
    config = get_config(TestEnvironment.LOCAL, base_url="http://custom:8080", verbose=False)
    print(f"Base URL: {config.base_url}")
    print(f"Verbose: {config.verbose}")

    # Show username generation
    print("\nTest Username Generation:")
    print("-" * 70)
    for i in range(3):
        username = generate_test_username()
        print(f"  {username}")

    # Show database path
    print("\nDatabase Path Examples:")
    print("-" * 70)
    local_config = get_config(TestEnvironment.LOCAL)
    print(f"  User 123 DB: {get_test_user_db_path(123, local_config)}")
    print(f"  Has local DB access: {local_config.has_local_db_access()}")

    staging_config = get_config(TestEnvironment.STAGING)
    print(f"  Staging has local DB access: {staging_config.has_local_db_access()}")

    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)
