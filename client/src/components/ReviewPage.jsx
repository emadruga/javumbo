import React, { useState, useEffect } from 'react';
import { getNextCard, answerCard } from '../api';
import { useNavigate } from 'react-router-dom';
import Header from './Header';

function ReviewPage({ user, onLogout }) {
  const [card, setCard] = useState(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [currentDeckName, setCurrentDeckName] = useState('Default');
  const [reviewMessage, setReviewMessage] = useState('Loading card...');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const storedDeckName = localStorage.getItem('currentDeckName');
    if (storedDeckName) {
      setCurrentDeckName(storedDeckName);
      setReviewMessage(`Reviewing: ${storedDeckName}`);
    } else {
      setReviewMessage('Reviewing: Default');
    }
  }, []);

  const fetchReviewData = async (isMounted) => {
    setError('');
    setReviewMessage(prev => prev.startsWith('Reviewing:') ? prev : `Reviewing: ${currentDeckName} - Loading card...`);
    try {
      const nextCardData = await getNextCard();
      console.log("ReviewPage: Successfully fetched next card data:", nextCardData);
      if (!isMounted) return;

      if (nextCardData && nextCardData.card_id) {
        setCard(nextCardData);
        setShowAnswer(false);
        setStartTime(Date.now());
        setReviewMessage(`Reviewing: ${currentDeckName}`);
      } else {
        setCard(null);
        setReviewMessage(nextCardData.message || `No cards due in deck: ${currentDeckName}.`);
      }
    } catch (err) {
      if (!isMounted) return;
      console.error("ReviewPage: Error fetching review data:", err);
      setError(err.response?.data?.error || 'Failed to load review session');
      setCard(null);
      setReviewMessage(`Error loading deck: ${currentDeckName}`);
    }
  };

  useEffect(() => {
    let isMounted = true;
    fetchReviewData(isMounted);

    return () => {
      isMounted = false;
    };
  }, []);

  const handleAnswer = async (ease) => {
    if (!card || !startTime) return;
    const timeTaken = Date.now() - startTime;
    setError('');
    setReviewMessage('Processing answer...');
    try {
      await answerCard({ ease: ease, time_taken: timeTaken });
      setCard(null);
      setReviewMessage(`Reviewing: ${currentDeckName} - Loading next card...`);
      let isMountedForNext = true;
      fetchReviewData(isMountedForNext);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to submit answer');
      setReviewMessage(`Error submitting answer for deck: ${currentDeckName}`);
    }
  };

  return (
    <div className="container mt-4">
      <Header user={user} onLogout={onLogout} />
      <h2>Review Cards</h2>
      {error && <div className="alert alert-danger mt-3">{error}</div>}
      
      {!error && reviewMessage && <p className="text-muted mt-2">{reviewMessage}</p>}

      {!error && card ? (
        <div className="card mt-3">
          <div className="card-body">
            <h5 className="card-title">Front</h5>
            <p className="card-text">{card.front}</p>
            {showAnswer && (
              <>
                <hr />
                <h5 className="card-title">Back</h5>
                <p className="card-text">{card.back}</p>
              </>
            )}
          </div>
          <div className="card-footer">
            {showAnswer ? (
              <div className="d-flex justify-content-around">
                <button className="btn btn-danger" onClick={() => handleAnswer(1)}>Again (1)</button>
                <button className="btn btn-warning" onClick={() => handleAnswer(2)}>Hard (2)</button>
                <button className="btn btn-success" onClick={() => handleAnswer(3)}>Good (3)</button>
                <button className="btn btn-primary" onClick={() => handleAnswer(4)}>Easy (4)</button>
              </div>
            ) : (
              <button className="btn btn-secondary" onClick={() => setShowAnswer(true)}>Show Answer</button>
            )}
          </div>
        </div>
      ) : (
        !error && !card && !reviewMessage && <p className="mt-3">Loading...</p>
      )}
    </div>
  );
}

export default ReviewPage; 