import sqlite3
import os
import json # Import the json library
from base_repository import BaseRepository

class DeckRepository(BaseRepository):

    def get_decks_by_user_id(self, user_id):
        """Retrieves all decks for a specific user (by user_id) by parsing the JSON in their Anki DB.
        
        Returns a list of dictionaries, each with 'id' and 'name'.
        Returns an empty list if the DB, table, or column is not found, or if parsing fails.
        """
        # Construct filename using user_id
        db_filename = f"user_{user_id}.db" 
        
        # Query the 'decks' JSON blob from the 'col' table
        query = "SELECT decks FROM col WHERE id = 1 LIMIT 1" 
        
        try:
            # Execute the query to get the single row from the 'col' table
            col_row = self._execute_query(db_filename, query, fetch_one=True)

            if not col_row:
                print(f"Could not find collection data in {db_filename} for user_id {user_id}.")
                return []

            # Parse the JSON string stored in the 'decks' column
            decks_json_string = col_row['decks']
            decks_data = json.loads(decks_json_string)
            
            # Extract id and name from each deck object in the JSON data
            deck_list = [
                {"id": deck_info['id'], "name": deck_info['name']} 
                for deck_info in decks_data.values()
            ]
            
            # Sort by name for consistency
            deck_list.sort(key=lambda x: x['name'])
            
            print(f"Successfully parsed {len(deck_list)} decks for user_id {user_id} from {db_filename}.")
            return deck_list

        except sqlite3.OperationalError as e:
            print(f"Database operational error getting decks for user_id {user_id} from {db_filename}: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing decks JSON for user_id {user_id} from {db_filename}: {e}")
            return []
        except KeyError as e:
            print(f"Missing key in decks JSON structure for user_id {user_id} from {db_filename}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting decks for user_id {user_id} from {db_filename}: {e}")
            return []

    # TODO: Add methods for creating, updating, deleting decks if needed by admin

# Instantiate repository
deck_repository = DeckRepository() 