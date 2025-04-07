import React, { useState, useEffect, useCallback } from 'react';
import Flashcard from '../components/Flashcard';
import Header from '../components/Header';
import api from '../api/axiosConfig';
import fileDownload from 'js-file-download'; // For handling file download

// Remove unused style constants
const pageStyle = {
  maxWidth: '700px',
  margin: '20px auto',
  padding: '0 20px',
  fontFamily: 'Arial, sans-serif'
};

const messageStyle = { textAlign: 'center', color: '#555', marginTop: '30px' };
const errorStyle = { textAlign: 'center', color: 'red', marginTop: '30px' };

function ReviewPage({ user, onLogout }) {
  const [currentCard, setCurrentCard] = useState(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const fetchNextCard = useCallback(async () => {
    setIsLoading(true);
    setShowAnswer(false);
    setMessage('');
    setError('');
    try {
      const response = await api.get('/review');
      if (response.data && response.data.card_id) {
        // Assuming backend is adjusted to send front and back
        setCurrentCard(response.data);
      } else {
        setCurrentCard(null);
        setMessage(response.data.message || "You've finished all cards for now!");
      }
    } catch (err) {
      console.error("Error fetching review card:", err);
      setError("Failed to load the next card. Please try again later.");
      setCurrentCard(null);
      if (err.response?.status === 401) {
        // Handle unauthorized access, e.g., redirect to login
        onLogout(); // Simple logout if session expired
      }
    } finally {
      setIsLoading(false);
    }
  }, [onLogout]); // Added onLogout dependency

  useEffect(() => {
    // Fetch the first card when the component mounts
    fetchNextCard();
  }, [fetchNextCard]);

  const handleShowAnswer = () => {
    setShowAnswer(true);
  };

  const handleAnswer = async (ease) => {
    if (!currentCard) return;

    setIsLoading(true); // Indicate processing
    const startTime = Date.now(); // Record time for backend (optional)

    try {
        const timeTaken = Date.now() - startTime;
        // Call the answer endpoint - assuming it just needs ease and handles session internally
        await api.post('/answer', { ease: ease, time_taken: timeTaken });
        // Fetch the next card immediately after answering
        fetchNextCard();
    } catch (err) {
        console.error("Error submitting answer:", err);
        setError("Failed to submit the answer. Please try again.");
        setIsLoading(false);
        if (err.response?.status === 401) {
           onLogout();
        }
    }
    // No finally setIsLoading(false) here, as fetchNextCard handles it
  };

  return (
    <div style={pageStyle}>
      <Header
        user={user}
        onLogout={onLogout}
      />

      <h1>Review Flashcards</h1>

      {isLoading && !currentCard && !message && !error && <p style={messageStyle}>Loading...</p>}
      {error && <p style={errorStyle}>{error}</p>}
      {message && !currentCard && <p style={messageStyle}>{message}</p>}

      {currentCard && (
        <Flashcard
          cardData={currentCard}
          showAnswer={showAnswer}
          onShowAnswer={handleShowAnswer}
          onAnswer={handleAnswer}
        />
      )}
    </div>
  );
}

export default ReviewPage; 