import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom'; // Import Link for navigation

function DeckList() {
  const { username } = useParams(); // Get username from URL parameter
  const [decks, setDecks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDecks = async () => {
      setIsLoading(true);
      setError(null);
      const apiUrl = `http://localhost:9000/users/${username}/decks`; // Use username in URL

      try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
          // Try to parse error message from backend
          let errorMsg = `HTTP error! status: ${response.status}`;
          try {
            const errorData = await response.json();
            errorMsg = errorData.error || errorMsg;
          } catch { /* Ignore parsing error */ }
          throw new Error(errorMsg);
        }
        const data = await response.json();
        setDecks(data);
      } catch (fetchError) {
        console.error(`Error fetching decks for ${username}:`, fetchError);
        setError(fetchError.message || 'Could not fetch decks.');
      } finally {
        setIsLoading(false);
      }
    };

    if (username) {
        fetchDecks();
    }

  }, [username]); // Re-run effect if username changes

  if (isLoading) {
    return <div>Loading decks for {username}...</div>;
  }

  if (error) {
    return <div style={{ color: 'red' }}>Error loading decks: {error}</div>;
  }

  return (
    <div>
      {/* Add a link back to the user list */} 
      <Link to="/users" style={{ display: 'block', marginBottom: '15px' }}>
        &larr; Back to User List
      </Link>
      
      <h2>Decks for {username}</h2>
      {decks.length === 0 ? (
        <p>No decks found for this user.</p>
      ) : (
        <ul>
          {decks.map(deck => (
            // Assuming deck object has 'id' and 'name' keys from the API
            <li key={deck.id}>{deck.name}</li> 
          ))}
        </ul>
      )}
      {/* TODO: Add actions for decks if needed */}
    </div>
  );
}

export default DeckList; 