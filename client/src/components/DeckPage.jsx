import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getDecks, createDeck, deleteDeck } from '../api';
import Header from './Header';

function DeckPage({ user, onLogout }) {
  const { t } = useTranslation();
  const [decks, setDecks] = useState([]);
  const [newDeckName, setNewDeckName] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchDecks();
  }, []);

  const fetchDecks = async () => {
    try {
      const fetchedDecks = await getDecks();
      setDecks(fetchedDecks);
    } catch (err) {
      console.error("Error fetching decks:", err);
      setError(t('decks.errorFetching'));
    }
  };

  const handleCreateDeck = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');

    if (!newDeckName.trim()) {
      setError(t('decks.errorNameRequired'));
      return;
    }

    try {
      await createDeck(newDeckName);
      setMessage(t('decks.createSuccess'));
      setNewDeckName('');
      fetchDecks();
    } catch (err) {
      console.error("Error creating deck:", err);
      setError(err.response?.data?.error || t('decks.errorCreating'));
    }
  };

  const handleDeleteDeck = async (deckId) => {
    if (window.confirm(t('decks.confirmDelete'))) {
      try {
        await deleteDeck(deckId);
        setMessage(t('decks.deleteSuccess'));
        fetchDecks();
      } catch (err) {
        console.error("Error deleting deck:", err);
        setError(err.response?.data?.error || t('decks.errorDeleting'));
      }
    }
  };

  const handleDeckSelect = (deckName) => {
    localStorage.setItem('currentDeckName', deckName);
    navigate('/review');
  };

  const handleAddCard = (deckName) => {
    localStorage.setItem('currentDeckName', deckName);
    navigate('/add-card');
  };

  return (
    <div className="container mt-4">
      <Header user={user} onLogout={onLogout} />
      <h2>{t('decks.title')}</h2>

      {message && <div className="alert alert-success mt-3">{message}</div>}
      {error && <div className="alert alert-danger mt-3">{error}</div>}

      <form onSubmit={handleCreateDeck} className="mb-4">
        <div className="input-group">
          <input
            type="text"
            className="form-control"
            value={newDeckName}
            onChange={(e) => setNewDeckName(e.target.value)}
            placeholder={t('decks.deckName')}
          />
          <button type="submit" className="btn btn-primary">
            {t('decks.createButton')}
          </button>
        </div>
      </form>

      {decks.length === 0 && (
        <p className="text-muted">{t('decks.noDecks')}</p>
      )}

      <div className="row">
        {decks.map((deck) => (
          <div key={deck.id} className="col-md-4 mb-3">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">{deck.name}</h5>
                <p className="card-text">
                  {t('decks.cardCount', { count: deck.cardCount || 0 })}
                </p>
                <div className="d-flex justify-content-between">
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleDeckSelect(deck.name)}
                  >
                    {t('decks.review')}
                  </button>
                  <button
                    className="btn btn-success btn-sm"
                    onClick={() => handleAddCard(deck.name)}
                  >
                    {t('decks.addCards')}
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleDeleteDeck(deck.id)}
                  >
                    {t('common.delete')}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default DeckPage; 