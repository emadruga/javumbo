import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header'; // Use shared header
import api from '../api/axiosConfig';
import fileDownload from 'js-file-download'; // Import for export
import { getDeckCards } from '../api'; // Import the new API function

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

// New styles for the card list view
const navbarStyle = {
  display: 'flex',
  gap: '20px',
  marginBottom: '20px',
  padding: '0 0 10px 0',
  borderBottom: '1px solid #ddd'
};

const navItemStyle = {
  padding: '8px 15px',
  cursor: 'pointer',
  borderRadius: '4px',
  fontSize: '1em',
  backgroundColor: '#f0f0f0'
};

const activeNavItemStyle = {
  ...navItemStyle,
  backgroundColor: '#007bff',
  color: 'white'
};

const cardListStyle = {
  listStyle: 'none',
  padding: 0,
  marginTop: '20px'
};

const cardItemStyle = {
  border: '1px solid #eee',
  marginBottom: '10px',
  borderRadius: '5px',
  overflow: 'hidden'
};

const cardHeaderStyle = {
  backgroundColor: '#f8f9fa',
  padding: '10px 15px',
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center'
};

const cardContentStyle = {
  padding: '15px',
  backgroundColor: 'white',
  borderTop: '1px solid #eee'
};

const paginationStyle = {
  display: 'flex',
  justifyContent: 'center',
  gap: '10px',
  marginTop: '20px'
};

const paginationButtonStyle = {
  ...buttonStyle,
  padding: '5px 10px'
};

function DecksPage({ user, onLogout }) {
  const [decks, setDecks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [newDeckName, setNewDeckName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isExporting, setIsExporting] = useState(false); // Add state for export
  const navigate = useNavigate();
  
  // New state for the card list view
  const [activeView, setActiveView] = useState('decks'); // 'decks' or 'cards'
  const [selectedDeck, setSelectedDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [isLoadingCards, setIsLoadingCards] = useState(false);
  const [cardsError, setCardsError] = useState('');
  const [expandedCardId, setExpandedCardId] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState({
    total: 0,
    per_page: 10,
    total_pages: 0
  });

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

  const fetchCards = useCallback(async (deckId, page = 1) => {
    if (!deckId) return;
    
    setIsLoadingCards(true);
    setCardsError('');
    try {
      const response = await getDeckCards(deckId, page);
      setCards(response.cards || []);
      setPagination(response.pagination || {
        total: 0,
        per_page: 10,
        total_pages: 0,
        page: 1
      });
      
      // Store the deck name for reference
      if (response.deck_name) {
        const deck = { id: response.deck_id, name: response.deck_name };
        setSelectedDeck(deck);
        localStorage.setItem('currentDeckName', response.deck_name);
      }
    } catch (err) {
      console.error("Error fetching cards:", err);
      setCardsError("Failed to load cards. Please try again later.");
      if (err.response?.status === 401) {
        onLogout();
      }
    } finally {
      setIsLoadingCards(false);
    }
  }, [onLogout]);

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
                 } catch {
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

  // Handler to view cards in a deck
  const handleViewCards = (deckId) => {
    setActiveView('cards');
    fetchCards(deckId, 1);
    setCurrentPage(1);
    setExpandedCardId(null);
  };

  // Handler to toggle card expansion
  const toggleCardExpansion = (cardId) => {
    if (expandedCardId === cardId) {
      setExpandedCardId(null);
    } else {
      setExpandedCardId(cardId);
    }
  };

  // Handler to edit a card
  const handleEditCard = (cardId) => {
    navigate(`/edit/${cardId}`);
  };

  // Handler for pagination
  const handlePageChange = (page) => {
    if (page < 1 || page > pagination.total_pages) return;
    setCurrentPage(page);
    fetchCards(selectedDeck?.id, page);
  };

  return (
    <div style={pageStyle}>
      {/* Pass null for onExport in Header */}
      <Header user={user} onLogout={onLogout} />

      {/* Navigation tabs */}
      <div style={navbarStyle}>
        <button 
          style={activeView === 'decks' ? activeNavItemStyle : navItemStyle}
          onClick={() => setActiveView('decks')}
        >
          Decks
        </button>
        {selectedDeck && (
          <button 
            style={activeView === 'cards' ? activeNavItemStyle : navItemStyle}
            onClick={() => handleViewCards(selectedDeck.id)}
          >
            Cards in {selectedDeck.name}
          </button>
        )}
      </div>

      {activeView === 'decks' ? (
        // DECKS VIEW
        <>
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
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      onClick={() => handleSelectDeck(deck.id)}
                      style={reviewButtonStyle}
                      className="btn btn-success btn-sm"
                    >
                      Review
                    </button>
                    <button
                      onClick={() => {
                        const deckName = deck.name || 'Unknown Deck';
                        localStorage.setItem('currentDeckName', deckName);
                        navigate(`/decks/${deck.id}/stats`);
                      }}
                      style={{...buttonStyle, backgroundColor: '#17a2b8'}}
                      className="btn btn-info btn-sm"
                    >
                      Stats
                    </button>
                    <button
                      onClick={() => handleViewCards(deck.id)}
                      style={{...buttonStyle, backgroundColor: '#6c757d'}}
                      className="btn btn-secondary btn-sm"
                    >
                      Browse
                    </button>
                  </div>
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
        </>
      ) : (
        // CARDS VIEW
        <>
          <h1>Cards in {selectedDeck?.name || 'Deck'}</h1>
          
          {isLoadingCards && <p>Loading cards...</p>}
          {cardsError && <p style={errorStyle}>{cardsError}</p>}
          
          {!isLoadingCards && (
            <>
              <ul style={cardListStyle}>
                {cards.map((card) => (
                  <li key={card.card_id} style={cardItemStyle}>
                    <div 
                      style={cardHeaderStyle}
                      onClick={() => toggleCardExpansion(card.card_id)}
                    >
                      <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {card.front.length > 60 ? card.front.substring(0, 60) + '...' : card.front}
                      </div>
                      <span>{expandedCardId === card.card_id ? '▲' : '▼'}</span>
                    </div>
                    
                    {expandedCardId === card.card_id && (
                      <div style={cardContentStyle}>
                        <div style={{ marginBottom: '15px' }}>
                          <h5>Front</h5>
                          <p>{card.front}</p>
                        </div>
                        <div style={{ marginBottom: '15px' }}>
                          <h5>Back</h5>
                          <p>{card.back}</p>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                          <button 
                            onClick={() => handleEditCard(card.card_id)}
                            style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}
                          >
                            Edit
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
                {cards.length === 0 && !cardsError && 
                  <p>No cards in this deck. Add some cards first!</p>
                }
              </ul>
              
              {/* Pagination */}
              {pagination.total_pages > 1 && (
                <div style={paginationStyle}>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(1)}
                    disabled={currentPage === 1}
                  >
                    First
                  </button>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    Prev
                  </button>
                  <span style={{ padding: '5px 10px' }}>
                    Page {currentPage} of {pagination.total_pages}
                  </span>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage === pagination.total_pages}
                  >
                    Next
                  </button>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(pagination.total_pages)}
                    disabled={currentPage === pagination.total_pages}
                  >
                    Last
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default DecksPage; 