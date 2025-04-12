# server/test_app.py
import unittest
import json
import os
import sqlite3
import bcrypt
import time
import shutil
from app import app, init_admin_db, init_anki_db, get_user_db_path, ADMIN_DB_PATH as APP_ADMIN_DB_PATH # Import your Flask app and init functions

# Use paths relative to the test file location (assuming test_app.py is in server/)
TEST_ADMIN_DB_PATH = 'test_admin.db'
TEST_USER_DB_DIR = 'test_user_dbs' # Directory to hold user test DBs

class TestFlaskApi(unittest.TestCase):

    def setUp(self):
        """Set up test client and initialize databases for each test."""
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key' # Use a fixed secret key for sessions

        # --- Configure Test Database Paths ---
        # IMPORTANT: Ensure your app functions can potentially use different paths
        # or that these configs override defaults effectively during tests.
        # For simplicity, we assume init functions accept path arguments
        # or we directly modify app state if needed (more complex).
        # Here, we'll just use local file names and manage them manually.
        self.admin_db_path = TEST_ADMIN_DB_PATH
        self.user_db_dir = TEST_USER_DB_DIR

        # Create user DB directory if it doesn't exist
        if not os.path.exists(self.user_db_dir):
            os.makedirs(self.user_db_dir)

        # Patch the get_user_db_path function for testing
        # (A more robust way might use unittest.mock.patch)
        self.original_get_user_db_path = app.view_functions.get('get_user_db_path') # Store original if needed
        try:
            import app as app_module
            self.original_get_user_db_path_func = app_module.get_user_db_path
            app_module.get_user_db_path = self._get_test_user_db_path # Override
        except (ImportError, AttributeError):
             print("Warning: Could not patch get_user_db_path globally. Test user DBs might not work as expected.")
             self.original_get_user_db_path_func = None

        # Store original admin path and set test path
        self.original_admin_db_path_in_app = APP_ADMIN_DB_PATH
        # Need to modify the actual variable used by init_admin_db
        # Assuming it was imported from app:
        import app as app_module
        app_module.ADMIN_DB_PATH = self.admin_db_path

        # Initialize admin DB using the now-overridden path
        init_admin_db() 

        self.client = app.test_client()

        # Register a test user - THIS will create the user DB via the endpoint logic
        register_response = self._register_user("testuser", "Test User", "password123")
        if register_response.status_code != 201:
            # If registration fails in setUp, subsequent tests will likely fail anyway
            raise Exception(f"Failed to register test user in setUp: {register_response.data}")
        self.test_user_id = json.loads(register_response.data)['user_id'] 
        
        # REMOVE explicit init_anki_db - registration handles it
        # init_anki_db(self._get_test_user_db_path(self.test_user_id), "Test User Deck")


    def tearDown(self):
        """Clean up database files and restore globals after each test."""
        # Clean up admin DB
        if os.path.exists(self.admin_db_path):
            os.remove(self.admin_db_path)

        # Clean up user DBs directory
        if os.path.exists(self.user_db_dir):
            shutil.rmtree(self.user_db_dir) # Recursively remove directory

        # Restore patched functions/variables if needed
        if self.original_get_user_db_path_func:
             try:
                 import app as app_module
                 app_module.get_user_db_path = self.original_get_user_db_path_func
             except (ImportError, AttributeError):
                 pass # Ignore if restoration fails

        # Restore original admin path
        try:
            import app as app_module
            app_module.ADMIN_DB_PATH = self.original_admin_db_path_in_app
        except (ImportError, AttributeError):
            pass # Ignore if restoration fails


    # --- Helper Methods ---
    def _get_test_user_db_path(self, user_id):
        """Helper to get path for test user DBs."""
        return os.path.join(self.user_db_dir, f'user_{user_id}.db')

    def _register_user(self, username, name, password):
        """Helper to register a user via API."""
        return self.client.post('/register', json={
            "username": username,
            "name": name,
            "password": password
        })

    def _login_user(self, username, password):
        """Helper to login a user and return the client context."""
        # Note: test_client manages cookies/session within the 'with' block
        return self.client.post('/login', json={
            "username": username,
            "password": password
        })

    def _create_deck(self, client_context, deck_name):
        """Helper to create a deck while logged in."""
        return client_context.post('/decks', json={'name': deck_name})

    def _add_card(self, client_context, front, back):
        """Helper to add a card while logged in."""
        # Increase sleep significantly to avoid timestamp collisions
        time.sleep(2) # 100 milliseconds
        return client_context.post('/add_card', json={'front': front, 'back': back})

    def _get_next_card(self, client_context):
         """Helper to get the next card for review."""
         return client_context.get('/review')

    def _answer_card(self, client_context, ease=3, time_taken=5000):
         """Helper to answer the current card."""
         return client_context.post('/answer', json={'ease': ease, 'time_taken': time_taken})


    # --- Test Cases ---

    # GET /
    def test_01_health_check(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Flashcard Server is Running!', response.data)

    # POST /register
    def test_02_register_success(self):
        response = self._register_user("newuser", "New User", "password1234")
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn("message", data)
        self.assertIn("user_id", data)
        # Check if user DB was created
        self.assertTrue(os.path.exists(self._get_test_user_db_path(data['user_id'])))

    def test_03_register_duplicate_username(self):
        response = self._register_user("testuser", "Another Test", "password123") # Already registered in setUp
        self.assertEqual(response.status_code, 409)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Username already exists")

    def test_04_register_missing_field(self):
        response = self.client.post('/register', json={"username": "nouser", "name": "No Name"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Missing required fields")

    # POST /login
    def test_05_login_success(self):
        with self.client as c: # Use context manager to handle session
            response = c.post('/login', json={"username": "testuser", "password": "password123"})
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn("message", data)
            self.assertIn("user", data)
            self.assertEqual(data["user"]["username"], "testuser")
            # Check if session is set by trying an authenticated route
            deck_response = c.get('/decks')
            self.assertEqual(deck_response.status_code, 200)

    def test_06_login_invalid_password(self):
        response = self._login_user("testuser", "wrongpassword")
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Invalid username or password")

    def test_07_login_nonexistent_user(self):
        response = self._login_user("nosuchuser", "password123")
        self.assertEqual(response.status_code, 401) # Should fail authorization

    # POST /logout
    def test_08_logout_success(self):
        with self.client as c:
            login_resp = self._login_user("testuser", "password123")
            self.assertEqual(login_resp.status_code, 200)
            # Check login worked
            deck_resp_before = c.get('/decks')
            self.assertEqual(deck_resp_before.status_code, 200)

            logout_resp = c.post('/logout')
            self.assertEqual(logout_resp.status_code, 200)
            data = json.loads(logout_resp.data)
            self.assertEqual(data["message"], "Logout successful")

            # Check logout worked
            deck_resp_after = c.get('/decks')
            self.assertEqual(deck_resp_after.status_code, 401) # Unauthorized

    def test_09_logout_not_logged_in(self):
        response = self.client.post('/logout')
        self.assertEqual(response.status_code, 200) # Should succeed gracefully

    # GET /decks
    def test_10_get_decks_success(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            response = c.get('/decks')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            # Assert against the name used during registration
            self.assertEqual(data[0]['name'], "Test User") 

    def test_11_get_decks_unauthorized(self):
        response = self.client.get('/decks')
        self.assertEqual(response.status_code, 401)

    # POST /decks
    def test_12_create_deck_success(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            response = self._create_deck(c, "My New Deck")
            self.assertEqual(response.status_code, 201)
            data = json.loads(response.data)
            self.assertIn("id", data)
            self.assertEqual(data["name"], "My New Deck")

            # Verify deck appears in list
            decks_list_resp = c.get('/decks')
            decks_list_data = json.loads(decks_list_resp.data)
            self.assertTrue(any(d['name'] == "My New Deck" for d in decks_list_data))
            self.assertEqual(len(decks_list_data), 2) # Default + new one

    def test_13_create_deck_duplicate_name(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            self._create_deck(c, "Duplicate Deck") # Create first time
            response = self._create_deck(c, "Duplicate Deck") # Create second time
            self.assertEqual(response.status_code, 409)

    def test_14_create_deck_empty_name(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            response = self._create_deck(c, "  ") # Empty name
            self.assertEqual(response.status_code, 400)

    # PUT /decks/current
    def test_15_set_current_deck_success(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            # Get default deck ID (usually '1' from init_anki_db)
            decks_resp = c.get('/decks')
            deck_id = json.loads(decks_resp.data)[0]['id']

            response = c.put('/decks/current', json={'deckId': deck_id})
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn("message", data)

    def test_16_set_current_deck_invalid_id(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            response = c.put('/decks/current', json={'deckId': 99999}) # Non-existent ID
            self.assertEqual(response.status_code, 404)

    def test_17_set_current_deck_missing_id(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            response = c.put('/decks/current', json={'name': 'wrong_key'}) # Missing deckId
            self.assertEqual(response.status_code, 400)

    # GET /review
    def test_21_get_next_card_success(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            self._add_card(c, "Q1", "A1") # Add a card to make sure one is available/new
            time.sleep(2) # Ensure card ID timestamp is unique enough
            self._add_card(c, "Q2", "A2")
            response = self._get_next_card(c)
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            # Should either be a card or a "no cards due" message
            self.assertTrue("card_id" in data or "message" in data)
            if "card_id" in data:
                self.assertIn("front", data)
                self.assertIn("back", data)

    def test_22_get_next_card_no_cards_available(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            
            max_reviews = 50 # Safety break to prevent infinite loop
            reviewed_count = 0
            
            while reviewed_count < max_reviews:
                get_resp = self._get_next_card(c) 
                self.assertEqual(get_resp.status_code, 200)
                get_data = json.loads(get_resp.data)

                if "card_id" in get_data:
                    # Found a card, answer it (e.g., 'Good')
                    print(f"(test_22) Reviewing card {get_data['card_id']}...") # Optional log
                    ans_resp = self._answer_card(c, ease=3) 
                    self.assertEqual(ans_resp.status_code, 200)
                    reviewed_count += 1
                    # Increase sleep significantly to avoid revlog.id collision
                    time.sleep(2) # 100 milliseconds 
                elif "message" in get_data:
                    # No more cards available, this is the expected end state
                    print(f"(test_22) Received message: {get_data['message']}")
                    break # Exit the loop
                else:
                    # Unexpected response format
                    self.fail("Unexpected response format from /review endpoint")
            
            # Assert that we broke because of a message, not the safety break
            self.assertLess(reviewed_count, max_reviews, "Safety break reached; review loop might be infinite.")

            # Verify the last response definitely contained a message
            final_get_resp = self._get_next_card(c)
            self.assertEqual(final_get_resp.status_code, 200)
            final_data = json.loads(final_get_resp.data)
            self.assertIn("message", final_data)
            self.assertNotIn("card_id", final_data)

    def test_23_get_next_card_unauthorized(self):
        response = self.client.get('/review')
        self.assertEqual(response.status_code, 401)

    # POST /answer
    def test_24_answer_card_success(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            self._add_card(c, "Q Ans", "A Ans")
            get_resp = self._get_next_card(c) # Load card into session
            self.assertEqual(json.loads(get_resp.data).get('queue'), 0) # Verify it's new

            response = self._answer_card(c, ease=4, time_taken=3000) # Answer Easy
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data["message"], "Answer processed successfully")

            # Optional: Verify card state changed in DB (more complex)

    def test_25_answer_card_invalid_ease(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            self._add_card(c, "Q Inv", "A Inv")
            self._get_next_card(c) # Load card into session
            response = self._answer_card(c, ease=5) # Invalid ease
            self.assertEqual(response.status_code, 400)

    def test_26_answer_card_no_card_in_session(self):
         with self.client as c:
            self._login_user("testuser", "password123")
            # DON'T call /review first
            response = self._answer_card(c, ease=3)
            self.assertEqual(response.status_code, 400) # Missing card info

    # GET /decks/<int:deck_id>/stats
    def test_27_get_stats_success(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            self._add_card(c, "StatQ", "StatA") # Add a card to deck 1
            deck_id = 1 # Default deck ID
            response = c.get(f'/decks/{deck_id}/stats')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn("counts", data)
            self.assertIn("total", data)
            self.assertIsInstance(data["counts"], dict)
            self.assertIsInstance(data["total"], int)
            self.assertGreaterEqual(data["total"], 1) # Should have at least the card we added
            self.assertGreaterEqual(data["counts"]["New"], 1) # Should be counted as new

    def test_28_get_stats_invalid_deck_id(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            response = c.get('/decks/9999/stats') # Non-existent deck
            self.assertEqual(response.status_code, 404)

    def test_29_get_stats_unauthorized(self):
        response = self.client.get('/decks/1/stats') # Needs login
        self.assertEqual(response.status_code, 401)

    # GET /export
    def test_30_export_success(self):
        with self.client as c:
            self._login_user("testuser", "password123")
            add_resp = self._add_card(c, "ExpQ", "ExpA") 
            self.assertEqual(add_resp.status_code, 201) # Ensure card was added
            
            response = c.get('/export')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'application/zip')
            self.assertIn('Content-Disposition', response.headers)
            # Remove double quote from assertion string
            self.assertIn('.apkg', response.headers['Content-Disposition']) 

    def test_31_export_unauthorized(self):
        response = self.client.get('/export')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
