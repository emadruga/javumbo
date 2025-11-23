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
export const answerCard = async ({ cardId, noteId, ease, timeTaken }) => {
  const response = await axiosInstance.post('/review', {
    cardId,
    noteId,
    ease,
    timeTaken
  });
  return response.data;
};

// Add a new card to the current deck
export const addCard = async ({ front, back }) => {
  const response = await axiosInstance.post('/cards', { front, back });
  return response.data;
};

// Get statistics for a specific deck
export const getDeckStats = async (deckId) => {
  const response = await axiosInstance.get(`/decks/${deckId}/stats`);
  return response.data; // Expected: { counts: {...}, total: number }
};

// Get a specific card by ID
export const getCard = async (cardId) => {
  const response = await axiosInstance.get(`/cards/${cardId}`);
  return response.data;
};

// Update a card
export const updateCard = async (cardId, { front, back }) => {
  const response = await axiosInstance.put(`/cards/${cardId}`, { front, back });
  return response.data;
};

// Get all cards for a specific deck with pagination
export const getDeckCards = async (deckId, page = 1, perPage = 10) => {
  const response = await axiosInstance.get(`/decks/${deckId}/cards`, {
    params: { page, perPage }
  });
  return response.data;
};

// Delete a card
export const deleteCard = async (cardId) => {
  const response = await axiosInstance.delete(`/cards/${cardId}`);
  return response.data;
};

// Register a new user
export const register = async ({ username, name, password }) => {
  const response = await axiosInstance.post('/register', {
    username,
    name,
    password
  });
  return response.data;
};