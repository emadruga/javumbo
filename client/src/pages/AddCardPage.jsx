import React, { useState } from 'react';
import Header from '../components/Header'; // Import shared header
import api from '../api/axiosConfig';

// Basic styling (consider moving to CSS)
const pageStyle = {
  maxWidth: '700px',
  margin: '20px auto',
  padding: '0 20px',
  fontFamily: 'Arial, sans-serif'
};

const formStyle = {
    border: '1px solid #eee',
    padding: '20px',
    backgroundColor: '#f9f9f9',
    borderRadius: '5px',
};

const labelStyle = {
    display: 'block',
    marginBottom: '5px',
    fontWeight: 'bold'
};

const textareaStyle = {
    width: 'calc(100% - 22px)', // Adjust for padding/border
    minHeight: '80px',
    padding: '10px',
    marginBottom: '15px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    fontSize: '1em',
    fontFamily: 'inherit' // Use page font
};

const buttonStyle = {
    padding: '10px 20px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '1em'
};

const messageStyle = { marginTop: '15px', fontWeight: 'bold' };
const successStyle = { ...messageStyle, color: 'green' };
const errorStyle = { ...messageStyle, color: 'red' };

function AddCardPage({ user, onLogout }) {
  const [front, setFront] = useState('');
  const [back, setBack] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');

    if (!front.trim() || !back.trim()) {
        setError('Both Front and Back fields are required.');
        return;
    }

    setLoading(true);
    try {
        const response = await api.post('/add_card', { front, back });
        setMessage('Card added successfully!');
        setFront(''); // Clear form on success
        setBack('');
        console.log('Add card response:', response.data);
        // Optional: Navigate back to review page or show feedback
        // navigate('/review');

    } catch (err) {
        console.error("Error adding card:", err);
        setMessage(''); // Clear success message
        if (err.response && err.response.data && err.response.data.error) {
            setError(err.response.data.error);
        } else {
            setError('Failed to add card. Please try again later.');
        }
         if (err.response?.status === 401) {
            onLogout(); // Logout if unauthorized
         }
    } finally {
        setLoading(false);
    }
  };

  return (
    <div style={pageStyle}>
      <Header user={user} onLogout={onLogout} /> {/* Use shared header - no export needed here */}

      <h1>Add New Flashcard</h1>

      <form onSubmit={handleSubmit} style={formStyle}>
        <div>
          <label htmlFor="front" style={labelStyle}>Front:</label>
          <textarea
            id="front"
            value={front}
            onChange={(e) => setFront(e.target.value)}
            style={textareaStyle}
            required
          />
        </div>
        <div>
          <label htmlFor="back" style={labelStyle}>Back:</label>
          <textarea
            id="back"
            value={back}
            onChange={(e) => setBack(e.target.value)}
            style={textareaStyle}
            required
          />
        </div>

        {message && <p style={successStyle}>{message}</p>}
        {error && <p style={errorStyle}>{error}</p>}

        <button type="submit" disabled={loading} style={buttonStyle}>
          {loading ? 'Adding...' : 'Add Card'}
        </button>
      </form>
    </div>
  );
}

export default AddCardPage; 