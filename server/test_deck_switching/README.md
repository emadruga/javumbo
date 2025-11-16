# Test Deck Switching - Automated Test Suite

This package provides automated testing infrastructure for reproducing and verifying the "lost cards" bug documented in the JAVUMBO flashcard application investigation reports.

## Purpose

The tests in this package are designed to:

1. **Reproduce** the exact bug conditions described in `docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md`
2. **Verify** that the backend maintains data integrity (no actual data loss)
3. **Identify** the frontend state management issues causing cards to become invisible
4. **Validate** bug fixes before deployment
5. **Prevent regression** through automated CI/CD testing

## Package Structure

```
test_deck_switching/
├── __init__.py                     # Package initialization and exports
├── base_test_client.py             # Reusable test client (mimics frontend)
├── config.py                       # Configuration for different environments
├── utils.py                        # Helper utilities and assertions
├── test_1_1_simple_switch.py       # Test 1.1: Simple Switch and Return
├── test_1_2_add_after_switch.py    # Test 1.2: Add Card After Switch
├── run_suite_1.py                  # Runner for Test Suite 1
└── README.md                       # This file
```

## Phase 1 Components (Completed)

### 1. `base_test_client.py`

A comprehensive test client that mimics frontend behavior:

- **Session Management**: Maintains cookies/session like a real browser
- **Authentication**: Login, logout, registration
- **Deck Operations**: Create, switch, delete, rename decks
- **Card Operations**: Add, retrieve, update, delete cards
- **Verification**: Check card counts, verify card existence
- **Logging**: Detailed API call logging for debugging

**Key Features**:
- Tracks current deck state (like frontend)
- Records all API calls for debugging
- Provides assertion methods for test validation
- Configurable verbosity for output

### 2. `config.py`

Configuration management for different test environments:

- **Predefined Environments**:
  - `LOCAL`: Testing against local development server (`http://localhost:5000`)
  - `STAGING`: Testing against staging server (`http://54.226.152.231`)
  - `PRODUCTION`: Testing against production server

- **Configuration Options**:
  - Base URL of API server
  - Database paths (for local testing with direct DB access)
  - Test user credentials and prefixes
  - Timing parameters (delays, timeouts)
  - Verbosity settings

- **Flexible Configuration**:
  - Environment variable support (`TEST_ENV`)
  - Command-line argument overrides
  - Custom environment support

### 3. `utils.py`

Helper utilities for test execution and reporting:

- **TestResult**: Class for tracking test execution and results
- **Assertion Helpers**: Specialized assertions for card/deck verification
- **Database Verification**: Direct SQLite queries for local testing
- **Report Generation**: JSON and Markdown output formats
- **Formatting**: Colored console output, headers, summaries
- **Timing**: Performance measurement utilities

## Installation

### Prerequisites

```bash
# Python 3.8+ required
python3 --version

# Install required packages
pip install requests
```

### Setup

The package is already in the correct location within the JAVUMBO project:

```bash
cd /Users/emadruga/proj/javumbo/server/test_deck_switching
```

## Usage

### Quick Start - Testing the Client

Each module can be run standalone for testing/demo purposes:

```bash
# Test the base client
python base_test_client.py

# Test the configuration module
python config.py

# Test the utilities module
python utils.py
```

### Using the Test Client in Your Own Tests

```python
from test_deck_switching import TestClient, get_config

# Get configuration
config = get_config()  # Uses TEST_ENV or defaults to LOCAL

# Create client
client = TestClient(config.base_url, "testuser", config.default_password)

# Login
client.login()

# Create cards
client.add_card("Question 1", "Answer 1")
client.add_card("Question 2", "Answer 2")

# Get decks
decks = client.get_decks()
default_deck = decks[0]

# Verify cards
cards = client.get_deck_cards(default_deck['id'])
print(f"Found {len(cards)} cards")

# Switch decks
new_deck = client.create_deck("Test Deck")
client.set_current_deck(new_deck['id'])

# Switch back
client.set_current_deck(default_deck['id'])

# Verify cards still exist (CRITICAL TEST!)
cards_after = client.get_deck_cards(default_deck['id'])
if len(cards_after) != len(cards):
    print("🔴 BUG DETECTED: Cards missing after deck switch!")
else:
    print("✅ All cards still present")

# Logout
client.logout()
```

### Using TestResult for Tracking

```python
from test_deck_switching import TestResult, format_test_header

# Create test result tracker
result = TestResult("1.1", "Simple Switch and Return")

print(format_test_header("1.1", "Simple Switch and Return"))

result.start()

# Run your test...
cards_expected = 10
cards_found = 10

result.add_assertion(
    description="Card count should match",
    passed=(cards_found == cards_expected),
    expected=cards_expected,
    actual=cards_found
)

result.end(
    status="PASS",
    cards_expected=cards_expected,
    cards_found=cards_found
)

print(result.to_string())
```

### Environment Configuration

```bash
# Use local environment (default)
export TEST_ENV=local
python your_test.py

# Use staging environment
export TEST_ENV=staging
python your_test.py

# Override base URL
python your_test.py --base-url http://custom-server.com
```

### Database Verification (Local Only)

For local testing, you can verify data integrity by directly querying the database:

```python
from test_deck_switching import verify_cards_in_database, get_test_user_db_path

config = get_config()  # Must be LOCAL environment

# Get database path
db_path = get_test_user_db_path(user_id=123, config=config)

# Verify cards in database
result = verify_cards_in_database(db_path, deck_id=1, expected_count=10)

if result['success']:
    print(f"Database has {result['actual_count']} cards")
    if result['matches']:
        print("✅ Count matches expectation")
    else:
        print("⚠️  Count mismatch!")
        print("This proves backend has correct data but frontend doesn't show it")
```

## Configuration Reference

### TestConfig Attributes

```python
config = get_config()

config.base_url              # "http://localhost:5000"
config.environment           # TestEnvironment.LOCAL
config.default_password      # "test_password_123"
config.test_user_prefix      # "test_deck_switching_"
config.card_creation_delay   # 0.1 (seconds between card creation)
config.verbose               # True (enable detailed logging)
config.timeout               # 10 (API call timeout in seconds)
config.admin_db_path         # "../test_admin.db" (local only)
config.user_db_dir           # "../test_user_dbs" (local only)
```

### Environment-Specific Settings

| Setting | Local | Staging | Production |
|---------|-------|---------|------------|
| Base URL | localhost:5000 | 54.226.152.231 | flashcards.example.com |
| DB Access | Yes | No | No |
| Default Password | test_password_123 | password123test | (secure) |
| Timeout | 10s | 15s | 20s |
| Verbose | True | True | False |

## Next Steps

### Phase 2: Implement Test Suite 1

Now that the foundation is complete, the next steps are:

1. **test_1_1_simple_switch.py** - Implement Test 1.1: Simple Switch and Return
2. **test_1_2_add_after_switch.py** - Implement Test 1.2: Add Card After Switch
3. **run_suite_1.py** - Create test runner for Suite 1

See `docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md` for detailed test specifications.

### Phase 3: Additional Test Suites

After Suite 1 is validated:

- Test Suite 2: Rapid/Multiple Switching (Rayssa & Gabrielle patterns)
- Test Suite 3: Time-Based Tests
- Test Suite 4: Session and Authentication
- ... (see comparative analysis for full list)

## Debugging

### Verbose Mode

All modules support verbose output for debugging:

```python
client = TestClient(base_url, username, password, verbose=True)
```

This will print:
- Every API request (method, endpoint, data)
- Every API response (status, data, timing)
- Deck switching operations
- Card verification results

### API Call History

The TestClient maintains a history of all API calls:

```python
# After running tests
print(client.get_api_call_summary())
```

Output:
```
API Call Summary:
  Total calls: 15
  Total time: 234ms
  Average time: 15ms
  Status codes: {200: 12, 201: 3}
```

### Test Result Details

TestResult objects capture detailed information:

```python
result = TestResult("1.1", "Simple Switch")
# ... run test ...

# Convert to dict for inspection
print(result.to_dict())

# Save to JSON
from test_deck_switching import save_test_results_json
save_test_results_json([result], "results.json")
```

## Troubleshooting

### "Connection refused" errors

Make sure your test server is running:

```bash
# For local testing
cd /Users/emadruga/proj/javumbo/server
python app.py
```

### "Module not found" errors

Make sure you're running from the correct directory:

```bash
cd /Users/emadruga/proj/javumbo/server
python -c "import test_deck_switching; print(test_deck_switching.__version__)"
```

### Database access errors (local tests)

Ensure database paths are correct in config:

```python
from test_deck_switching import get_config

config = get_config()
print(f"Admin DB: {config.admin_db_path}")
print(f"User DB dir: {config.user_db_dir}")
```

## Contributing

When adding new tests:

1. Follow the naming convention: `test_X_Y_description.py`
2. Use TestResult for tracking
3. Provide clear assertion messages
4. Include both success and failure scenarios
5. Document expected behavior vs actual behavior
6. Reference the comparative analysis document

## Related Documentation

- [docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md](../../../docs/LOST_CARDS_COMPARATIVE_ANALYSIS.md) - Detailed bug analysis
- [docs/LOST_CARDS_INVESTIGATION_SUMMARY.md](../../../docs/LOST_CARDS_INVESTIGATION_SUMMARY.md) - Investigation summary
- [docs/LOST_CARDS_REPRODUCTION_PLAN.md](../../../docs/LOST_CARDS_REPRODUCTION_PLAN.md) - Original reproduction plan
- [docs/REST_API.md](../../../docs/REST_API.md) - API documentation

## License

Part of the JAVUMBO project.

## Version History

- **1.0.0** (November 2025) - Initial implementation
  - Base test client
  - Configuration management
  - Utility functions
  - Ready for Test Suite 1 implementation
