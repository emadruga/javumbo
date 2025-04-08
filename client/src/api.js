import axiosInstance from './api/axiosConfig.js'; // Correct path to the file in the api directory

// Fetch all decks
export const getDecks = async () => {
  const response = await axiosInstance.get('/decks');
  return response.data; 
};

// Set the current deck
export const setDeck = async (deckId) => {
  const response = await axiosInstance.put('/decks/current', { deck_id: deckId });
  return response.data;
};

// Get the next card for review in the current deck
export const getNextCard = async () => {
  const response = await axiosInstance.get('/review');
  return response.data;
};

// Answer a review card
export const answerCard = async ({ ease, time_taken }) => {
  // card_id is implicitly handled by the server session/state for the current card
  const response = await axiosInstance.post('/answer', { ease, time_taken });
  return response.data;
};

// Add a new card to the current deck
export const addCard = async ({ front, back }) => {
  const response = await axiosInstance.post('/add_card', { front, back });
  return response.data;
};

// Get statistics for a specific deck
export const getDeckStats = async (deckId, timeframe = 'today') => {
  // Note: Backend currently ignores timeframe parameter
  const response = await axiosInstance.get(`/decks/${deckId}/stats`, {
    // params: { timeframe } // Send timeframe if backend uses it
  });
  return response.data; // Expected: { counts: {...}, total: number }
}; 