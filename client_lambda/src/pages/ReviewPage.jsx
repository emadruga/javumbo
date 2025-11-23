import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { getNextCard, answerCard } from "../api";
import Header from "../components/Header";

function ReviewPage() {
  const { t } = useTranslation();
  const { username, logout } = useAuth();
  const [card, setCard] = useState(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [currentDeckName, setCurrentDeckName] = useState('');
  const [reviewMessage, setReviewMessage] = useState(t('common.loading'));
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const storedDeckName = localStorage.getItem('currentDeckName');
    if (storedDeckName) {
      setCurrentDeckName(storedDeckName);
      setReviewMessage(`${t('review.reviewing')}: ${storedDeckName}`);
    }
  }, [t]);

  const fetchReviewData = async (isMounted) => {
    setError('');
    setReviewMessage(prev =>
      prev.startsWith(t('review.reviewing'))
        ? prev
        : `${t('review.reviewing')}: ${currentDeckName} - ${t('common.loading')}`
    );

    try {
      const nextCardData = await getNextCard();
      if (!isMounted) return;

      if (nextCardData && nextCardData.cardId) {
        setCard(nextCardData);
        setShowAnswer(false);
        setStartTime(Date.now());
        setReviewMessage(`${t('review.reviewing')}: ${currentDeckName}`);
      } else {
        setCard(null);
        setReviewMessage(nextCardData?.message || t('review.noCardsMessage', { deckName: currentDeckName }));
      }
    } catch (err) {
      if (!isMounted) return;
      console.error("Error fetching review data:", err);
      setError(err.response?.data?.error || t('review.errorLoading'));
      setCard(null);
      setReviewMessage(t('review.errorLoadingDeck', { deckName: currentDeckName }));

      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      }
    }
  };

  useEffect(() => {
    let isMounted = true;
    fetchReviewData(isMounted);
    return () => {
      isMounted = false;
    };
  }, [currentDeckName, t]);

  const handleAnswer = async (ease) => {
    if (!card || !startTime) return;
    const timeTaken = Date.now() - startTime;
    setError('');
    setReviewMessage(t('review.processingAnswer'));

    try {
      await answerCard({
        cardId: card.cardId,
        noteId: card.noteId,
        ease: ease,
        timeTaken: timeTaken
      });
      setCard(null);
      setReviewMessage(`${t('review.reviewing')}: ${currentDeckName} - ${t('common.loading')}`);
      let isMountedForNext = true;
      fetchReviewData(isMountedForNext);
    } catch (err) {
      setError(err.response?.data?.error || t('review.errorSubmitting'));
      setReviewMessage(t('review.errorSubmittingAnswer', { deckName: currentDeckName }));

      if (err.response?.status === 401) {
        logout();
        navigate('/login');
      }
    }
  };

  const handleBackToDecks = () => {
    navigate('/decks');
  };

  return (
    <div className="container mt-4">
      <Header user={{ username }} onLogout={() => { logout(); navigate('/login'); }} />
      <div className="d-flex justify-content-between align-items-center">
        <h2>{t('review.title')}</h2>
        <button
          className="btn btn-secondary"
          onClick={handleBackToDecks}
        >
          {t('review.backToDecks')}
        </button>
      </div>

      {error && <div className="alert alert-danger mt-3">{error}</div>}
      {!error && reviewMessage && <p className="text-muted mt-2">{reviewMessage}</p>}

      {!error && card && (
        <div className="card mt-3">
          <div className="card-body">
            <h5 className="card-title">{t('cards.front')}</h5>
            <p className="card-text">{card.front}</p>
            {showAnswer && (
              <>
                <hr />
                <h5 className="card-title">{t('cards.back')}</h5>
                <p className="card-text">{card.back}</p>
              </>
            )}
          </div>
          <div className="card-footer">
            {showAnswer ? (
              <div className="d-flex justify-content-around mb-2">
                <button className="btn btn-danger" onClick={() => handleAnswer(1)}>
                  {t('review.again')} (1)
                </button>
                <button className="btn btn-warning" onClick={() => handleAnswer(2)}>
                  {t('review.hard')} (2)
                </button>
                <button className="btn btn-success" onClick={() => handleAnswer(3)}>
                  {t('review.good')} (3)
                </button>
                <button className="btn btn-primary" onClick={() => handleAnswer(4)}>
                  {t('review.easy')} (4)
                </button>
              </div>
            ) : (
              <div className="d-flex justify-content-between">
                <button className="btn btn-secondary" onClick={() => setShowAnswer(true)}>
                  {t('review.showAnswer')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReviewPage;
