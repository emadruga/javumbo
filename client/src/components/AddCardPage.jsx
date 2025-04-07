import React, { useState } from 'react';
import { addCard } from '../api';
import { useNavigate } from 'react-router-dom';
import Header from './Header';

function AddCardPage({ user, onLogout }) {
  const [front, setFront] = useState('');
  const [back, setBack] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (!front.trim() || !back.trim()) {
      setError('Front and back cannot be empty.');
      return;
    }

    try {
      const response = await addCard({ front, back });
      setMessage(`Card added successfully (ID: ${response.card_id})!`);
      setFront('');
      setBack('');
      // Optionally navigate away or give user time to see the message
      // setTimeout(() => navigate('/decks'), 1500); 
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to add card');
    }
  };

  return (
    <div className="container mt-4">
      <Header user={user} onLogout={onLogout} />
      <h2>Add New Card</h2>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label htmlFor="front" className="form-label">Front</label>
          <textarea
            id="front"
            className="form-control"
            rows="3"
            value={front}
            onChange={(e) => setFront(e.target.value)}
            required
          />
        </div>
        <div className="mb-3">
          <label htmlFor="back" className="form-label">Back</label>
          <textarea
            id="back"
            className="form-control"
            rows="3"
            value={back}
            onChange={(e) => setBack(e.target.value)}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary">Add Card</button>
      </form>
    </div>
  );
}

export default AddCardPage; 