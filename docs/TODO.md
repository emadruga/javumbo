# Refactoring Plan: OOP Implementation With Database Module

## Revised Refactoring Plan (Without Changing API Routes)

### Phase 1: Create Database Module
1. Create the database module structure
2. Extract SQL operations to appropriate DAO files
3. Ensure backward compatibility with existing SQL operations

### Phase 2: Create OOP Model Classes
1. Implement model classes that use the new DAOs
2. Ensure they implement the same business logic as before
3. Test models with the same inputs/outputs as original functions

### Phase 3: Refactor app.py Incrementally
1. Update app.py to use the new models **without changing routes**
2. Replace direct SQL operations with model method calls
3. Update one route handler at a time while preserving route paths and parameters

### Phase 4: Final Integration and Testing
1. Ensure all route handlers are using the new models
2. Verify no changes to the API contract
3. Run all existing tests to ensure compatibility

## Implementation Details

The key difference in this approach is that we'll:

1. **Keep all route definitions in app.py** exactly as they are
2. **Preserve all URL paths and parameters** as defined in REST_API.md
3. **Maintain identical request/response formats** to ensure compatibility

Example for a route refactoring (within app.py):

Before:
```python
@app.route('/decks', methods=['GET'])
@login_required
def get_decks():
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    # Direct SQL operations...
    conn = sqlite3.connect(db_path)
    # More SQL code...
    
    return jsonify(result)
```

After:
```python
@app.route('/decks', methods=['GET'])
@login_required
def get_decks():
    user_id = session['user_id']
    
    # Use the model instead of direct SQL
    deck_model = DeckModel(user_id)
    result = deck_model.get_all_decks()
    
    return jsonify(result)
```

This approach lets us completely refactor the implementation while keeping the API contract untouched. Any client using the API would see no difference, and the REST_API.md documentation remains valid.