import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header'; // Use shared header
import api from '../api/axiosConfig';
import fileDownload from 'js-file-download'; // Import for export

// Basic styling (consider moving to CSS)
const pageStyle = {
  maxWidth: '900px',
  margin: '20px auto',
  padding: '0 20px',
  fontFamily: 'Arial, sans-serif'
};

const deckListStyle = {
  listStyle: 'none',
  padding: 0,
};

const deckItemStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '15px',
  border: '1px solid #eee',
  marginBottom: '10px',
  borderRadius: '5px',
  backgroundColor: '#fdfdfd'
};

const deckNameStyle = {
  fontSize: '1.2em',
  fontWeight: 'bold'
};

const buttonStyle = {
    padding: '8px 15px',
    cursor: 'pointer',
    borderRadius: '4px',
    border: '1px solid #ccc',
    fontSize: '1em'
};

const reviewButtonStyle = {...buttonStyle, backgroundColor: '#28a745', color: 'white'};
const exportButtonStyle = {...buttonStyle, backgroundColor: '#6c757d', color: 'white'}; // Add style for export button
const createFormStyle = {
    display: 'flex',
    gap: '10px',
    marginTop: '20px',
    padding: '15px',
    border: '1px solid #ccc',
    borderRadius: '5px', 
    backgroundColor: '#f8f9fa'
};
const inputStyle = {
    flexGrow: 1,
    padding: '8px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    fontSize: '1em'
};
const createButtonStyle = {...buttonStyle, backgroundColor: '#007bff', color: 'white'};
const messageStyle = { marginTop: '15px', fontWeight: 'bold' };
const errorStyle = { ...messageStyle, color: 'red' };

function DecksPage({ user, onLogout }) {
  const [decks, setDecks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [newDeckName, setNewDeckName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isExporting, setIsExporting] = useState(false); // Add state for export
  const navigate = useNavigate();

  const fetchDecks = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await api.get('/decks');
      setDecks(response.data || []);
    } catch (err) {
      console.error("Error fetching decks:", err);
      setError("Failed to load decks. Please try again later.");
      if (err.response?.status === 401) {
        onLogout();
      }
    } finally {
      setIsLoading(false);
    }
  }, [onLogout]);

  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  const handleCreateDeck = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) {
        setError('Deck name cannot be empty.');
        return;
    }
    setIsCreating(true);
    setError('');
    try {
        await api.post('/decks', { name: newDeckName.trim() });
        setNewDeckName(''); // Clear input
        fetchDecks(); // Refresh deck list
    } catch (err) {
        console.error("Error creating deck:", err);
        if (err.response && err.response.data && err.response.data.error) {
            setError(err.response.data.error);
        } else {
            setError('Failed to create deck.');
        }
         if (err.response?.status === 401) {
            onLogout();
         }
    } finally {
        setIsCreating(false);
    }
  };

  const handleSelectDeck = async (deckId) => {
    // Optional: Add loading state for selection
    setError('');
    try {
        await api.put('/decks/current', { deckId });
        console.log(`Set current deck to ${deckId}`);

        // Find the deck name from the state
        const selectedDeck = decks.find(deck => deck.id === deckId);
        const deckName = selectedDeck ? selectedDeck.name : 'Unknown Deck';

        // Store the name in localStorage
        localStorage.setItem('currentDeckName', deckName);
        console.log(`Stored current deck name '${deckName}' in localStorage.`);

        navigate('/review'); // Navigate to review page for the selected deck
    } catch (err) {
        console.error("Error setting current deck:", err);
         setError('Failed to select deck. Please try again.');
         if (err.response?.status === 401) {
            onLogout();
         }
    }
  };

  // Add export handler (copied & adapted from previous ReviewPage)
  const handleExport = async () => {
      setIsExporting(true);
      setError(''); // Clear previous errors
      try {
          const response = await api.get('/export', {
              responseType: 'blob',
          });
          const contentDisposition = response.headers['content-disposition'];
          let filename = 'flashcard_export.apkg';
          if (contentDisposition) {
              const filenameMatch = contentDisposition.match(/filename="?([^;"]+)"?/);
              if (filenameMatch && filenameMatch[1]) {
                  filename = filenameMatch[1];
              }
          }
          fileDownload(response.data, filename);
          alert('Export successful! Check your downloads.');
      } catch (err) {
          console.error("Export error:", err);
          if (err.response?.status === 401) {
             onLogout();
          } else {
             // Attempt to read error from blob if it's JSON
             if (err.response && err.response.data && err.response.data instanceof Blob && err.response.data.type === "application/json") {
                 try {
                     const errorJson = JSON.parse(await err.response.data.text());
                     setError(errorJson.error || 'Export failed.');
                 } catch (parseError) {
                     setError('Export failed. Unable to parse server error response.');
                 }
             } else {
                 setError('Export failed. Please try again.');
             }
          }
      } finally {
          setIsExporting(false);
      }
  };

  return (
    <div style={pageStyle}>
      {/* Pass null for onExport in Header */}
      <Header user={user} onLogout={onLogout} />

      <h1>Your Decks</h1>

      {/* Add Export Button Here */}
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'flex-end' }}>
         <button onClick={handleExport} disabled={isExporting} style={exportButtonStyle}> 
             {isExporting ? 'Exporting...' : 'Export Collection'}
         </button>
      </div>

      {isLoading && <p>Loading decks...</p>}
      {error && <p style={errorStyle}>{error}</p>}

      {!isLoading && (
        <ul style={deckListStyle}>
          {decks.map((deck) => (
            <li key={deck.id} style={deckItemStyle}>
              <span style={deckNameStyle}>{deck.name}</span>
              <button
                onClick={() => handleSelectDeck(deck.id)}
                style={reviewButtonStyle}
              >
                Review
              </button>
            </li>
          ))}
          {decks.length === 0 && !error && <p>You don't have any decks yet. Create one below!</p>}
        </ul>
      )}

      <form onSubmit={handleCreateDeck} style={createFormStyle}>
        <input
            type="text"
            value={newDeckName}
            onChange={(e) => setNewDeckName(e.target.value)}
            placeholder="New deck name"
            style={inputStyle}
            required
        />
        <button type="submit" disabled={isCreating} style={createButtonStyle}>
            {isCreating ? 'Creating...' : 'Create Deck'}
        </button>
      </form>

    </div>
  );
}

export default DecksPage; 