import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { getCard, updateCard } from '../api'; // Import the API functions

// Basic styling (matching AddCardPage)
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
    fontSize: '1em',
    marginRight: '10px'
};

const cancelButtonStyle = {
    ...buttonStyle,
    backgroundColor: '#6c757d',
};

const messageStyle = { marginTop: '15px', fontWeight: 'bold' };
const successStyle = { ...messageStyle, color: 'green' };
const errorStyle = { ...messageStyle, color: 'red' };

function EditCardPage({ user, onLogout }) {
  const { cardId } = useParams();
  const navigate = useNavigate();
  
  const [front, setFront] = useState('');
  const [back, setBack] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(true);

  // Fetch the card data when component mounts
  useEffect(() => {
    const fetchCardData = async () => {
      setFetchLoading(true);
      setError('');
      try {
        const cardData = await getCard(cardId);
        setFront(cardData.front);
        setBack(cardData.back);
      } catch (err) {
        console.error("Error fetching card:", err);
        if (err.response && err.response.data && err.response.data.error) {
          setError(err.response.data.error);
        } else {
          setError('Failed to load card data. Please try again later.');
        }
        if (err.response?.status === 401) {
          onLogout();
        }
      } finally {
        setFetchLoading(false);
      }
    };

    if (cardId) {
      fetchCardData();
    }
  }, [cardId, onLogout]);

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
        await updateCard(cardId, { front, back });
        setMessage('Card updated successfully!');
        // Wait a moment to show the success message before navigating
        setTimeout(() => {
          navigate(-1); // Go back to previous page
        }, 1500);
    } catch (err) {
        console.error("Error updating card:", err);
        setMessage(''); // Clear success message
        if (err.response && err.response.data && err.response.data.error) {
            setError(err.response.data.error);
        } else {
            setError('Failed to update card. Please try again later.');
        }
        if (err.response?.status === 401) {
            onLogout();
        }
    } finally {
        setLoading(false);
    }
  };

  const handleCancel = () => {
    navigate(-1); // Go back to previous page
  };

  if (fetchLoading) {
    return (
      <div style={pageStyle}>
        <Header user={user} onLogout={onLogout} />
        <h1>Edit Flashcard</h1>
        <p>Loading card data...</p>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <Header user={user} onLogout={onLogout} />

      <h1>Edit Flashcard</h1>

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

        <div style={{ display: 'flex' }}>
          <button type="submit" disabled={loading} style={buttonStyle}>
            {loading ? 'Updating...' : 'Update Card'}
          </button>
          <button type="button" onClick={handleCancel} style={cancelButtonStyle}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

export default EditCardPage; 