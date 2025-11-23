import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useDBSession } from '../hooks/useDBSession';
import Header from '../components/Header'; // Use shared header
import SessionIndicator from '../components/SessionIndicator';
import api from '../api/axiosConfig';
import fileDownload from 'js-file-download'; // Import for export
import { getDeckCards, deleteCard } from '../api'; // Import API functions
import '@fontsource/material-icons';

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
  padding: '5px 10px',
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  fontFamily: 'Material Icons',
  fontSize: '24px',  // Adjust size for Material Icons
  lineHeight: '1'    // Ensure proper vertical alignment
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

function DecksPage() {
  const { t } = useTranslation();
  const { username, logout } = useAuth();
  const navigate = useNavigate();

  // Session management hook
  const {
    sessionId,
    isActive,
    error: sessionError,
    getTimeRemaining,
  } = useDBSession();

  const [decks, setDecks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [newDeckName, setNewDeckName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isExporting, setIsExporting] = useState(false); // Add state for export
  
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
    perPage: 10,
    totalPages: 0
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
  
  // Function to add a card to a specific deck
  const handleAddCard = async (deckId, deckName) => {
    setError('');
    try {
      // Set the current deck
      await api.put('/decks/current', { deckId });
      // Store deck name for AddCardPage
      localStorage.setItem('currentDeckName', deckName);
      // Navigate to the add card page
      navigate('/add');
    } catch (err) {
      console.error("Error setting current deck:", err);
      setError(t('decks.errorSelectingDeck'));
      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      }
    }
  };

  // Function to handle dropdown menu item clicks
  const handleDropdownAction = async (e, action, deck) => {
    e.stopPropagation(); // Prevent event from bubbling up
    setOpenDropdownId(null);
    
    switch (action) {
      case 'review':
        handleSelectDeck(deck.id, deck.name);
        break;
      case 'stats':
        localStorage.setItem('currentDeckName', deck.name || 'Unknown Deck');
        navigate(`/decks/${deck.id}/stats`);
        break;
      case 'browse':
        handleViewCards(deck.id);
        break;
      case 'rename':
        handleDeckRenameClick(deck.id, deck.name);
        break;
      case 'addCard':
        handleAddCard(deck.id, deck.name);
        break;
      case 'delete':
        handleDeckDeleteClick(deck.id, deck.name);
        break;
      default:
        console.warn('Unknown action:', action);
    }
  };

  const fetchDecks = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await api.get('/decks');
      setDecks(response.data.decks || []);
    } catch (err) {
      console.error("Error fetching decks:", err);
      setError(t('decks.errorFetching'));
      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      }
    } finally {
      setIsLoading(false);
    }
  }, [logout, navigate, t]);

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
        perPage: 10,
        totalPages: 0,
        page: 1
      });
      
      // Store the deck name for reference
      if (response.deckName) {
        const deck = { id: response.deckId, name: response.deckName };
        setSelectedDeck(deck);
        localStorage.setItem('currentDeckName', response.deckName);
      }
    } catch (err) {
      console.error("Error fetching cards:", err);
      setCardsError("Failed to load cards. Please try again later.");
      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      }
    } finally {
      setIsLoadingCards(false);
    }
  }, [logout, navigate]);

  const handleCreateDeck = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) {
      setError(t('decks.errorNameRequired'));
      return;
    }

    setIsCreating(true);
    setError('');
    try {
      await api.post('/decks', { name: newDeckName });
      setNewDeckName('');
      fetchDecks();
    } catch (err) {
      console.error("Error creating deck:", err);
      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError(t('decks.errorCreating'));
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handleSelectDeck = async (deckId, deckName) => {
    setError('');
    try {
        await api.put('/decks/current', { deckId });
        console.log(`Set current deck to ${deckName}`);

        // Store the name in localStorage
        localStorage.setItem('currentDeckName', deckName);
        console.log(`Stored current deck name '${deckName}' in localStorage.`);

        navigate('/review'); // Navigate to review page for the selected deck
    } catch (err) {
        console.error("Error setting current deck:", err);
        setError(t('decks.errorSelectingDeck'));
        if (err.response?.status === 401) {
            logout();
        navigate('/login');
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
             logout();
        navigate('/login');
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
    if (page < 1 || page > pagination.totalPages) return;
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
      await deleteCard(cardToDelete.cardId);
      // Remove card from state
      setCards(cards.filter(card => card.cardId !== cardToDelete.cardId));
      // Update pagination
      setPagination(prev => ({
        ...prev,
        total: prev.total - 1,
        totalPages: Math.max(1, Math.ceil((prev.total - 1) / prev.perPage))
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
        logout();
        navigate('/login');
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
        logout();
        navigate('/login');
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
        logout();
        navigate('/login');
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError("Failed to rename deck. Please try again.");
      }
    } finally {
      setIsRenaming(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mt-4">
        <Header user={{ username }} onLogout={() => { logout(); navigate('/login'); }} />
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <Header user={{ username }} onLogout={() => { logout(); navigate('/login'); }} />

      <div>
        <div style={navbarStyle}>
          <button 
            style={activeView === 'decks' ? activeNavItemStyle : navItemStyle}
            onClick={() => setActiveView('decks')}
          >
            {t('decks.decks')}
          </button>
          {selectedDeck && (
            <button 
              style={activeView === 'cards' ? activeNavItemStyle : navItemStyle}
              onClick={() => handleViewCards(selectedDeck.id)}
            >
              {t('decks.cardsIn', { deckName: selectedDeck.name })}
            </button>
          )}
        </div>
      </div>

      {activeView === 'decks' ? (
        <>
          <h1>{t('decks.title')}</h1>

          <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={handleExport} disabled={isExporting} style={exportButtonStyle}> 
                {isExporting ? t('common.exporting') : t('decks.exportCollection')}
            </button>
          </div>

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
                          onClick={(e) => handleDropdownAction(e, 'review', deck)}
                        >
                          {t('decks.review')}
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#17a2b8'}}
                          onClick={(e) => handleDropdownAction(e, 'stats', deck)}
                        >
                          {t('decks.statistics')}
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#6c757d'}}
                          onClick={(e) => handleDropdownAction(e, 'browse', deck)}
                        >
                          {t('decks.browse')}
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#ffc107'}}
                          onClick={(e) => handleDropdownAction(e, 'rename', deck)}
                        >
                          {t('decks.rename')}
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#007bff'}}
                          onClick={(e) => handleDropdownAction(e, 'addCard', deck)}
                        >
                          {t('cards.add')}
                        </button>
                        <button 
                          style={{...dropdownItemStyle, color: '#dc3545'}}
                          onClick={(e) => handleDropdownAction(e, 'delete', deck)}
                        >
                          {t('common.delete')}
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              ))}
              {decks.length === 0 && !error && <p>{t('decks.noDecks')}</p>}
            </ul>
          )}

          <form onSubmit={handleCreateDeck} style={createFormStyle}>
            <input
                type="text"
                value={newDeckName}
                onChange={(e) => setNewDeckName(e.target.value)}
                placeholder={t('decks.deckNamePlaceholder')}
                style={inputStyle}
                required
                title={t('decks.errorNameRequired')}
            />
            <button type="submit" disabled={isCreating} style={createButtonStyle}>
                {isCreating ? t('common.loading') : t('decks.createButton')}
            </button>
          </form>

          {/* Session indicator */}
          {sessionError && (
            <div className="alert alert-danger mt-3">
              <strong>Session Error:</strong> {sessionError}
            </div>
          )}
          {isActive && (
            <div style={{ marginTop: '20px' }}>
              <SessionIndicator
                isActive={isActive}
                getTimeRemaining={getTimeRemaining}
                onFlush={null}
              />
            </div>
          )}
        </>
      ) : (
        <>
          <h1>{t('decks.cardsIn', { deckName: selectedDeck?.name || t('decks.deck') })}</h1>
          
          {isLoadingCards && <p>{t('common.loading')}</p>}
          {cardsError && <p style={errorStyle}>{cardsError}</p>}
          
          {!isLoadingCards && (
            <>
              <ul style={cardListStyle}>
                {cards.map((card) => (
                  <li key={card.cardId} style={cardItemStyle}>
                    <div 
                      style={cardHeaderStyle}
                      onClick={() => toggleCardExpansion(card.cardId)}
                    >
                      <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {card.front.length > 60 ? card.front.substring(0, 60) + '...' : card.front}
                      </div>
                      <span>{expandedCardId === card.cardId ? '▲' : '▼'}</span>
                    </div>
                    
                    {expandedCardId === card.cardId && (
                      <div style={cardContentStyle}>
                        <div style={{ marginBottom: '15px' }}>
                          <h5>{t('decks.front')}</h5>
                          <p>{card.front}</p>
                        </div>
                        <div style={{ marginBottom: '15px' }}>
                          <h5>{t('decks.back')}</h5>
                          <p>{card.back}</p>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                          <button 
                            onClick={() => handleEditCard(card.cardId)}
                            style={{...buttonStyle, backgroundColor: '#007bff', color: 'white'}}
                          >
                            {t('cards.edit')}
                          </button>
                          <button 
                            onClick={() => handleDeleteClick(card)}
                            style={deleteButtonStyle}
                          >
                            {t('common.delete')}
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
                {cards.length === 0 && !cardsError && 
                  <p>{t('decks.noCards')}</p>
                }
              </ul>
              
              {pagination.totalPages > 1 && (
                <div style={paginationStyle}>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(1)}
                    disabled={currentPage === 1}
                    title={t('common.first')}
                  >
                    first_page
                  </button>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    title={t('common.prev')}
                  >
                    navigate_before
                  </button>
                  <span style={{ padding: '5px 10px' }}>
                    {t('decks.page', { currentPage, totalPages: pagination.totalPages })}
                  </span>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage === pagination.totalPages}
                    title={t('common.next')}
                  >
                    navigate_next
                  </button>
                  <button 
                    style={paginationButtonStyle}
                    onClick={() => handlePageChange(pagination.totalPages)}
                    disabled={currentPage === pagination.totalPages}
                    title={t('common.last')}
                  >
                    last_page
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {showDeleteModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>{t('common.deleteCard')}</h3>
            <p>{t('decks.confirmDeleteCard')}</p>
            {cardToDelete && (
              <div style={{ backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '4px', margin: '10px 0' }}>
                <strong>{t('decks.front')}:</strong> {cardToDelete.front.length > 50 
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
                {t('common.cancel')}
              </button>
              <button 
                onClick={handleConfirmDelete}
                style={deleteButtonStyle}
                disabled={isDeleting}
              >
                {isDeleting ? t('common.deleting') : t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeckDeleteModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>{t('common.deleteDeck')}</h3>
            <p>{t('decks.confirmDeleteDeck')}</p>
            {deckToDelete && (
              <div style={{ backgroundColor: '#f8f9fa', padding: '10px', borderRadius: '4px', margin: '10px 0' }}>
                <strong>{t('decks.deck')}:</strong> {deckToDelete.name}
              </div>
            )}
            <div style={modalButtonsStyle}>
              <button 
                onClick={handleCancelDeckDelete}
                style={buttonStyle}
                disabled={isDeckDeleting}
              >
                {t('common.cancel')}
              </button>
              <button 
                onClick={handleConfirmDeckDelete}
                style={deleteButtonStyle}
                disabled={isDeckDeleting}
              >
                {isDeckDeleting ? t('common.deleting') : t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeckRenameModal && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>{t('decks.renameDeck')}</h3>
            <p>{t('decks.enterNewName')}</p>
            {deckToRename && (
              <div style={{ marginBottom: '15px' }}>
                <strong>{t('decks.currentName')}:</strong> {deckToRename.name}
              </div>
            )}
            <div style={{ marginBottom: '20px' }}>
              <input
                type="text"
                value={newDeckRename}
                onChange={(e) => setNewDeckRename(e.target.value)}
                placeholder={t('decks.enterNewName')}
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
                {t('common.cancel')}
              </button>
              <button 
                onClick={handleConfirmDeckRename}
                style={{...buttonStyle, backgroundColor: '#ffc107', color: 'black'}}
                disabled={isRenaming || !newDeckRename.trim()}
              >
                {isRenaming ? t('common.renaming') : t('decks.rename')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DecksPage; 