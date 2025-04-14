import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header'; // Use shared header
import api from '../api/axiosConfig';
import fileDownload from 'js-file-download'; // Import for export
import { getDeckCards, deleteCard } from '../api'; // Import API functions

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
  gap: '15px',
  marginBottom: '20px',
  padding: '10px 0',
  borderBottom: '1px solid #e0e0e0'
};

const navItemStyle = {
  padding: '6px 15px',
  cursor: 'pointer',
  borderRadius: '4px',
  fontSize: '0.95em',
  backgroundColor: '#f8f9fa',
  border: '1px solid #ddd',
  fontWeight: 'normal'
};

const activeNavItemStyle = {
  ...navItemStyle,
  backgroundColor: '#e9f2ff',
  borderColor: '#b8daff',
  color: '#007bff',
  fontWeight: 'bold',
  borderBottom: '2px solid #007bff'
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

// New styles for confirmation modal
const modalOverlayStyle = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 1000
};

const modalContentStyle = {
  backgroundColor: 'white',
  padding: '20px',
  borderRadius: '5px',
  maxWidth: '500px',
  width: '90%',
  boxShadow: '0 2px 10px rgba(0, 0, 0, 0.2)'
};

const modalButtonsStyle = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: '10px',
  marginTop: '20px'
};

const deleteButtonStyle = {
  ...buttonStyle,
  backgroundColor: '#dc3545',
  color: 'white'
};

// Add new styles for the dropdown menu
const dropdownButtonStyle = {
  ...buttonStyle,
  backgroundColor: '#6c757d',
  color: 'white',
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  padding: '8px 10px'
};

const dropdownMenuStyle = {
  position: 'absolute',
  backgroundColor: 'white',
  border: '1px solid #ddd',
  borderRadius: '4px',
  boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
  zIndex: 10,
  marginTop: '2px',
  right: '0',
  minWidth: '120px'
};

const dropdownItemStyle = {
  padding: '8px 15px',
  cursor: 'pointer',
  display: 'block',
  width: '100%',
  textAlign: 'left',
  border: 'none',
  backgroundColor: 'transparent',
  borderBottom: '1px solid #eee'
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

  // New state for the delete confirmation modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [cardToDelete, setCardToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // New state for deck deletion
  const [showDeckDeleteModal, setShowDeckDeleteModal] = useState(false);
  const [deckToDelete, setDeckToDelete] = useState(null);
  const [isDeckDeleting, setIsDeckDeleting] = useState(false);

  // New state for deck renaming
  const [showDeckRenameModal, setShowDeckRenameModal] = useState(false);
  const [deckToRename, setDeckToRename] = useState(null);
  const [newDeckRename, setNewDeckRename] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);

  // Add state for dropdown
  const [openDropdownId, setOpenDropdownId] = useState(null);
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setOpenDropdownId(null);
    };
    
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, []);
  
  // Function to toggle dropdown menu
  const toggleDropdown = (e, deckId) => {
    e.stopPropagation(); // Prevent event from bubbling up
    setOpenDropdownId(openDropdownId === deckId ? null : deckId);
  };
  
  // Function to handle dropdown menu item clicks
  const handleDropdownAction = (e, action, deckId, deckName) => {
    e.stopPropagation(); // Prevent event from bubbling up
    setOpenDropdownId(null);
    
    switch(action) {
      case 'review':
        handleSelectDeck(deckId);
        break;
      case 'stats':
        localStorage.setItem('currentDeckName', deckName || 'Unknown Deck');
        navigate(`/decks/${deckId}/stats`);
        break;
      case 'browse':
        handleViewCards(deckId);
        break;
      case 'rename':
        handleDeckRenameClick(deckId, deckName);
        break;
      case 'delete':
        handleDeckDeleteClick(deckId, deckName);
        break;
      default:
        break;
    }
  };

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

  // Handler to open delete confirmation modal
  const handleDeleteClick = (card) => {
    setCardToDelete(card);
    setShowDeleteModal(true);
  };

  // Handler to cancel delete
  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setCardToDelete(null);
  };

  // Handler to confirm delete
  const handleConfirmDelete = async () => {
    if (!cardToDelete) return;
    
    setIsDeleting(true);
    try {
      await deleteCard(cardToDelete.card_id);
      // Remove card from state
      setCards(cards.filter(card => card.card_id !== cardToDelete.card_id));
      // Update pagination
      setPagination(prev => ({
        ...prev,
        total: prev.total - 1,
        total_pages: Math.max(1, Math.ceil((prev.total - 1) / prev.per_page))
      }));
      // Close modal
      setShowDeleteModal(false);
      setCardToDelete(null);
      // Fetch cards again if we've deleted the last card on the page
      if (cards.length === 1 && currentPage > 1) {
        fetchCards(selectedDeck?.id, currentPage - 1);
        setCurrentPage(currentPage - 1);
      }
    } catch (err) {
      console.error("Error deleting card:", err);
      if (err.response?.status === 401) {
        onLogout();
      } else {
        setCardsError("Failed to delete card. Please try again.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  // Handler to open deck delete confirmation modal
  const handleDeckDeleteClick = (deckId, deckName) => {
    setDeckToDelete({ id: deckId, name: deckName });
    setShowDeckDeleteModal(true);
  };

  // Handler to cancel deck delete
  const handleCancelDeckDelete = () => {
    setShowDeckDeleteModal(false);
    setDeckToDelete(null);
  };

  // Handler to confirm deck delete
  const handleConfirmDeckDelete = async () => {
    if (!deckToDelete) return;
    
    setIsDeckDeleting(true);
    try {
      await api.delete(`/decks/${deckToDelete.id}`);
      // Remove deck from state
      setDecks(decks.filter(deck => deck.id !== deckToDelete.id));
      // Close modal
      setShowDeckDeleteModal(false);
      setDeckToDelete(null);
      
      // If the deleted deck was the selected deck, reset the selection
      if (selectedDeck && selectedDeck.id === deckToDelete.id) {
        setSelectedDeck(null);
        setActiveView('decks');
      }
    } catch (err) {
      console.error("Error deleting deck:", err);
      if (err.response?.status === 401) {
        onLogout();
      } else {
        setError("Failed to delete deck. Please try again.");
      }
    } finally {
      setIsDeckDeleting(false);
    }
  };

  // Handler to open deck rename modal
  const handleDeckRenameClick = (deckId, deckName) => {
    setDeckToRename({ id: deckId, name: deckName });
    setNewDeckRename(deckName);
    setShowDeckRenameModal(true);
  };

  // Handler to cancel deck rename
  const handleCancelDeckRename = () => {
    setShowDeckRenameModal(false);
    setDeckToRename(null);
    setNewDeckRename('');
  };

  // Handler to confirm deck rename
  const handleConfirmDeckRename = async () => {
    if (!deckToRename || !newDeckRename.trim()) return;
    
    setIsRenaming(true);
    try {
      await api.put(`/decks/${deckToRename.id}/rename`, { name: newDeckRename.trim() });
      
      // Update the deck name in the local state
      setDecks(decks.map(deck => 
        deck.id === deckToRename.id 
          ? { ...deck, name: newDeckRename.trim() } 
          : deck
      ));
      
      // If this was the selected deck, update that reference too
      if (selectedDeck && selectedDeck.id === deckToRename.id) {
        setSelectedDeck({ ...selectedDeck, name: newDeckRename.trim() });
        localStorage.setItem('currentDeckName', newDeckRename.trim());
      }
      
      // Close modal
      setShowDeckRenameModal(false);
      setDeckToRename(null);
      setNewDeckRename('');
      
    } catch (err) {
      console.error("Error renaming deck:", err);
      if (err.response?.status === 401) {
        onLogout();
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError("Failed to rename deck. Please try again.");
      }
    } finally {
      setIsRenaming(false);
    }
  };

  return (
    <div style={pageStyle}>
      {/* Pass null for onExport in Header */}
      <Header user={user} onLogout={onLogout} />

      {/* Navigation tabs */}
      <div>
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
                  <div style={{ position: 'relative' }}>
                    <button
                      onClick={(e) => toggleDropdown(e, deck.id)}
                      style={dropdownButtonStyle}
                    >
                      &#9881;
                      <span style={{ marginLeft: '2px' }}>▼</span>
                    </button>
                    
                    {openDropdownId === deck.id && (
                      <div style={dropdownMenuStyle}>
                        <button 
                          style={{...dropdownItemStyle, color: '#28a745'}}
                          onClick={(e) => handleDropdownAction(e, 'review', deck.id, deck.name)}
                        >
                          Review
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#17a2b8'}}
                          onClick={(e) => handleDropdownAction(e, 'stats', deck.id, deck.name)}
                        >
                          Stats
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#6c757d'}}
                          onClick={(e) => handleDropdownAction(e, 'browse', deck.id, deck.name)}
                        >
                          Browse
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#ffc107'}}
                          onClick={(e) => handleDropdownAction(e, 'rename', deck.id, deck.name)}
                        >
                          Rename
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#dc3545'}}
                          onClick={(e) => handleDropdownAction(e, 'delete', deck.id, deck.name)}
                        >
                          Delete
                        </button>
                      </div>
                    )}
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
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                          <button 
                            onClick={() => handleEditCard(card.card_id)}
                            style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}
                          >
                            Edit
                          </button>
                          <button 
                            onClick={() => handleDeleteClick(card)}
                            style={deleteButtonStyle}
                          >
                            Delete
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

      {/* Delete Card Confirmation Modal */}
      {showDeleteModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>Delete Card</h3>
            <p>Are you sure you want to delete this card?</p>
            {cardToDelete && (
              <div style={{ backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '4px', margin: '10px 0' }}>
                <strong>Front:</strong> {cardToDelete.front.length > 50 
                  ? cardToDelete.front.substring(0, 50) + '...' 
                  : cardToDelete.front}
              </div>
            )}
            <div style={modalButtonsStyle}>
              <button 
                onClick={handleCancelDelete}
                style={buttonStyle}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button 
                onClick={handleConfirmDelete}
                style={deleteButtonStyle}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Deck Confirmation Modal */}
      {showDeckDeleteModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>Delete Deck</h3>
            <p>Are you sure you want to delete this deck? This will delete all cards in the deck and cannot be undone.</p>
            {deckToDelete && (
              <div style={{ backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '4px', margin: '10px 0' }}>
                <strong>Deck:</strong> {deckToDelete.name}
              </div>
            )}
            <div style={modalButtonsStyle}>
              <button 
                onClick={handleCancelDeckDelete}
                style={buttonStyle}
                disabled={isDeckDeleting}
              >
                Cancel
              </button>
              <button 
                onClick={handleConfirmDeckDelete}
                style={deleteButtonStyle}
                disabled={isDeckDeleting}
              >
                {isDeckDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Deck Modal */}
      {showDeckRenameModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>Rename Deck</h3>
            <p>Enter a new name for this deck:</p>
            {deckToRename && (
              <div style={{ marginBottom: '15px' }}>
                <strong>Current name:</strong> {deckToRename.name}
              </div>
            )}
            <div style={{ marginBottom: '20px' }}>
              <input
                type="text"
                value={newDeckRename}
                onChange={(e) => setNewDeckRename(e.target.value)}
                placeholder="Enter new deck name"
                style={{...inputStyle, width: '100%'}}
                required
              />
            </div>
            <div style={modalButtonsStyle}>
              <button 
                onClick={handleCancelDeckRename}
                style={buttonStyle}
                disabled={isRenaming}
              >
                Cancel
              </button>
              <button 
                onClick={handleConfirmDeckRename}
                style={{...buttonStyle, backgroundColor: '#ffc107', color: 'black'}}
                disabled={isRenaming || !newDeckRename.trim()}
              >
                {isRenaming ? 'Renaming...' : 'Rename'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DecksPage; 