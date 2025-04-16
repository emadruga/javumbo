import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { addCard } from "../api";
import Header from "../components/Header";

function AddCardPage({ user, onLogout }) {
  const { t } = useTranslation();
  const [front, setFront] = useState('');
  const [back, setBack] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [currentDeckName, setCurrentDeckName] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const storedDeckName = localStorage.getItem('currentDeckName');
    if (storedDeckName) {
      setCurrentDeckName(storedDeckName);
    } else {
      navigate('/decks');
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');

    if (!front.trim() || !back.trim()) {
      setError(t('cards.errorRequired'));
      return;
    }

    try {
      await addCard({ front, back });
      setMessage(t('cards.addSuccess'));
      setFront('');
      setBack('');
    } catch (err) {
      console.error("Error adding card:", err);
      setError(err.response?.data?.error || t('cards.errorAdding'));
    }
  };

  const handleBackToDecks = () => {
    navigate('/decks');
  };

  return (
    <div className="container mt-4">
      <Header user={user} onLogout={onLogout} />
      <div className="d-flex justify-content-between align-items-center">
        <h2>{t('cards.addTo')} {currentDeckName}</h2>
        <button 
          className="btn btn-secondary"
          onClick={handleBackToDecks}
        >
          {t('common.back')}
        </button>
      </div>

      {message && <div className="alert alert-success mt-3">{message}</div>}
      {error && <div className="alert alert-danger mt-3">{error}</div>}

      <form onSubmit={handleSubmit} className="mt-4">
        <div className="mb-3">
          <label htmlFor="front" className="form-label">{t('cards.front')}</label>
          <textarea
            id="front"
            className="form-control"
            value={front}
            onChange={(e) => setFront(e.target.value)}
            rows="3"
            placeholder={t('cards.frontPlaceholder')}
          />
        </div>

        <div className="mb-3">
          <label htmlFor="back" className="form-label">{t('cards.back')}</label>
          <textarea
            id="back"
            className="form-control"
            value={back}
            onChange={(e) => setBack(e.target.value)}
            rows="3"
            placeholder={t('cards.backPlaceholder')}
          />
        </div>

        <div className="d-flex justify-content-between">
          <button type="submit" className="btn btn-primary">
            {t('cards.add')}
          </button>
          <button 
            type="button" 
            className="btn btn-secondary" 
            onClick={handleBackToDecks}
          >
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </div>
  );
}

export default AddCardPage; 