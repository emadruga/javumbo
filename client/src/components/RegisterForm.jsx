import React, { useState } from 'react';
import api from '../api/axiosConfig';

const inputStyle = {
  display: 'block',
  width: 'calc(100% - 20px)', // Account for padding
  padding: '8px',
  marginBottom: '10px',
  border: '1px solid #ccc',
  borderRadius: '4px'
};

const buttonStyle = {
  padding: '10px 20px',
  backgroundColor: '#007bff',
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer'
};

const errorStyle = {
  color: 'red',
  marginBottom: '10px'
};

function RegisterForm({ onRegisterSuccess }) {
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); // Clear previous errors

    // Basic frontend validation
    if (!username || !name || !password || !confirmPassword) {
      setError('All fields are required.');
      return;
    }
    if (username.length > 10) {
        setError('Username cannot exceed 10 characters.');
        return;
    }
    if (name.length > 40) {
        setError('Name cannot exceed 40 characters.');
        return;
    }
    if (password.length < 10 || password.length > 20) {
      setError('Password must be between 10 and 20 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/register', {
        username,
        name,
        password,
      });
      console.log('Registration successful:', response.data);
      alert('Registration successful! Please log in.'); // Give feedback
      if (onRegisterSuccess) {
        onRegisterSuccess(); // Callback to switch tab
      }
      // Clear form
      setUsername('');
      setName('');
      setPassword('');
      setConfirmPassword('');

    } catch (err) {
      console.error('Registration error:', err);
      if (err.response && err.response.data && err.response.data.error) {
        setError(err.response.data.error);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Register</h2>
      {error && <p style={errorStyle}>{error}</p>}
      <label htmlFor="reg-username">Username (max 10 chars):</label>
      <input
        type="text"
        id="reg-username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        maxLength="10"
        required
        style={inputStyle}
      />
      <label htmlFor="reg-name">Name (max 40 chars):</label>
      <input
        type="text"
        id="reg-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength="40"
        required
        style={inputStyle}
      />
      <label htmlFor="reg-password">Password (10-20 chars):</label>
      <input
        type="password"
        id="reg-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        minLength="10"
        maxLength="20"
        required
        style={inputStyle}
      />
      <label htmlFor="reg-confirm-password">Confirm Password:</label>
      <input
        type="password"
        id="reg-confirm-password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        required
        style={inputStyle}
      />
      <button type="submit" disabled={loading} style={buttonStyle}>
        {loading ? 'Registering...' : 'Register'}
      </button>
    </form>
  );
}

export default RegisterForm; 