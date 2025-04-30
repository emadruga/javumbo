# Unit Testing the Flashcard API

This document outlines the process for running and extending the unit tests for the Flashcard Application's REST API.

## Test Structure

The test suite uses Python's built-in `unittest` framework to test all API endpoints. The main test file is located at:

```
server/test_api.py
```

Key components of the test structure:

- **TestFlaskApi class**: Main test class that inherits from `unittest.TestCase`
- **setUp method**: Configures testing environment before each test, including:
  - Setting up test databases
  - Registering a test user
  - Patching necessary functions
- **tearDown method**: Cleans up after each test, removing test databases
- **Helper methods**: Simplify common operations like user registration and login
- **Test cases**: Individual test methods that verify specific API functionality

## Running the Tests

### Prerequisites

1. Make sure you have all dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Navigate to the server directory:
   ```bash
   cd flashcard-app-v5-anki-gemini/server
   ```

### Running All Tests

To run the complete test suite:

```bash
python test_api.py
```

Or using the unittest module directly:

```bash
python -m unittest test_api.py
```

### Running Specific Tests

To run a specific test or group of tests, use the `-k` flag with a pattern:

```bash
python -m unittest test_api.py -k test_37_rename_deck
```

### Detailed Test Output

For more detailed output, use the `-v` (verbose) flag:

```bash
python -m unittest test_api.py -v
```

## Understanding Test Organization

The tests follow a consistent naming convention:

- `test_XX_feature_success`: Tests successful operation of a feature
- `test_XXa_feature_error_case`: Tests error handling for the same feature

Tests are organized by endpoint/feature:

1. **Health Check** (test_01_health_check)
2. **User Registration** (test_02_register_success through test_04_register_missing_field)
3. **Login/Logout** (test_05_login_success through test_09_logout_not_logged_in)
4. **Deck Management** (test_10_get_decks_success through test_17_set_current_deck_missing_id)
5. **Card Review** (test_21_get_next_card_success through test_26_answer_card_no_card_in_session)
6. **Statistics** (test_27_get_stats_success through test_29_get_stats_unauthorized)
7. **Export** (test_30_export_success through test_31_export_unauthorized)
8. **Card CRUD Operations** (test_32_get_card_details_success through test_35b_delete_card_unauthorized)
9. **Advanced Deck Operations** (test_36_delete_deck_success through test_37d_rename_deck_unauthorized)

## Writing New Tests

When adding new endpoints or features, add corresponding tests following these guidelines:

1. **Test both success and error cases** for each endpoint
2. **Use helper methods** to reduce code duplication
3. **Follow naming conventions** to keep tests organized
4. **Document test purpose** with clear method names and comments

### Test Template

```python
def test_XX_feature_name_success(self):
    with self.client as c:
        # 1. Setup (login, create required data)
        self._login_user("testuser", "password123")
        
        # 2. Execute the API call being tested
        response = c.get('/your-endpoint')
        
        # 3. Assert status code
        self.assertEqual(response.status_code, 200)
        
        # 4. Parse and validate response data
        data = json.loads(response.data)
        self.assertIn("expected_field", data)
        
        # 5. Optionally verify database state
        # ...
```

## Common Testing Patterns

### Authentication Testing

Most endpoints require authentication. Test both authenticated and unauthenticated access:

```python
# Authenticated
def test_endpoint_success(self):
    with self.client as c:
        self._login_user("testuser", "password123")
        response = c.get('/protected-endpoint')
        self.assertEqual(response.status_code, 200)

# Unauthenticated
def test_endpoint_unauthorized(self):
    response = self.client.get('/protected-endpoint')
    self.assertEqual(response.status_code, 401)
```

### Testing Data Creation

When testing endpoints that modify data, verify both the response and the resulting data state:

```python
def test_create_resource(self):
    with self.client as c:
        self._login_user("testuser", "password123")
        
        # Create the resource
        response = c.post('/resource', json={'name': 'Test'})
        self.assertEqual(response.status_code, 201)
        
        # Verify resource was created by trying to fetch it
        resource_id = json.loads(response.data)["id"]
        get_resp = c.get(f'/resource/{resource_id}')
        self.assertEqual(get_resp.status_code, 200)
```

## Troubleshooting

### Common Issues

1. **Database errors**: The test suite uses separate test databases, but issues can occur if paths aren't properly isolated.
   - Check the `setUp` and `tearDown` methods to ensure proper database initialization and cleanup.

2. **Session handling**: Some tests may fail if Flask session handling isn't working correctly.
   - Ensure you're using the context manager (`with self.client as c:`) for tests requiring login.

3. **Missing dependencies**: If tests crash unexpectedly, check that all required packages are installed.

4. **Port conflicts**: If the API server is already running on the default port, some tests might fail.
   - Stop any running instances of the API server before running tests.

### Debugging Tests

To aid in debugging, you can add print statements within test methods:

```python
def test_problematic_endpoint(self):
    with self.client as c:
        self._login_user("testuser", "password123")
        response = c.get('/problematic-endpoint')
        print(f"Response data: {response.data}")
        # ... rest of test
```

## Further Reading

For more information about unit testing in Python and Flask-specific testing techniques, refer to these resources:

### Python unittest
- [Official Python unittest Documentation](https://docs.python.org/3/library/unittest.html) - Comprehensive guide to Python's built-in testing framework
- [Python Testing with unittest](https://realpython.com/python-testing/) - Real Python's detailed tutorial on unittest
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html) - How to use mocks in Python tests

### Flask Testing
- [Flask Testing Documentation](https://flask.palletsprojects.com/en/2.3.x/testing/) - Official Flask documentation on testing
- [Testing Flask Applications](https://testdriven.io/blog/flask-pytest/) - TestDriven.io's guide to testing Flask apps
- [Advanced Flask Testing](https://www.patricksoftwareblog.com/testing-a-flask-application-using-pytest/) - Advanced patterns for Flask app testing

### Testing Best Practices
- [The Hitchhiker's Guide to Python: Testing](https://docs.python-guide.org/writing/tests/) - Best practices for Python testing
- [Python Testing 101](https://www.codecademy.com/article/tdd-python) - Introduction to Test-Driven Development in Python
- [WebTest](https://docs.pylonsproject.org/projects/webtest/en/latest/) - WSGI application testing tool that can be used with Flask

---

By following these guidelines, you can effectively test the Flashcard Application's REST API endpoints, ensuring the application works as expected even as new features are added. 