import React, { useState } from 'react';
import api from '../api/axiosConfig.js'; // Make sure path is correct

// Restore styles
const inputStyle = {
  display: 'block',
  width: 'calc(100% - 20px)',
  padding: '8px',
  marginBottom: '10px',
  border: '1px solid #ccc',
  borderRadius: '4px'
};
const buttonStyle = {
  padding: '10px 20px',
  backgroundColor: '#28a745', // Different color for login
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer'
};
const errorStyle = {
  color: 'red',
  marginBottom: '10px'
};

function LoginForm({ onLoginSuccess }) {
  // Restore state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Restore handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!username || !password) {
      setError('Username and password are required.');
      setLoading(false);
      return;
    }

    try {
      const response = await api.post('/login', {
        username,
        password,
      });
      console.log('Login response:', response.data);
      if (onLoginSuccess) {
        onLoginSuccess(response.data.user); // Pass user data up to App.jsx
      }
      // No need to clear form, as we navigate away
    } catch (err) {
      console.error('Login error:', err);
      if (err.response && err.response.data && err.response.data.error) {
        setError(err.response.data.error);
      } else {
        setError('Login failed. Please check credentials or server status.');
      }
      setLoading(false);
    }
  };

  console.log("Rendering full LoginForm...");

  return (
    // Restore form elements
    <form onSubmit={handleSubmit}>
      <h2>Login</h2>
      {error && <p style={errorStyle}>{error}</p>}
      <label htmlFor="login-username">Username:</label>
      <input
        type="text"
        id="login-username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
        style={inputStyle}
      />
      <label htmlFor="login-password">Password:</label>
      <input
        type="password"
        id="login-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        style={inputStyle}
      />
      <button type="submit" disabled={loading} style={buttonStyle}>
        {loading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}

export default LoginForm; 