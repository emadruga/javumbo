import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Basic frontend validation
    if (!username || !name || !password || !confirmPassword) {
      setError(t('auth.errors.required'));
      return;
    }
    if (username.length > 10) {
      setError(t('auth.errors.usernameLength', { max: 10 }));
      return;
    }
    if (name.length > 40) {
      setError(t('auth.errors.nameLength', { max: 40 }));
      return;
    }
    if (password.length < 10 || password.length > 20) {
      setError(t('auth.errors.passwordLength', { min: 10, max: 20 }));
      return;
    }
    if (password !== confirmPassword) {
      setError(t('auth.errors.passwordMatch'));
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
      alert(t('auth.successRegister'));
      if (onRegisterSuccess) {
        onRegisterSuccess();
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
        setError(t('auth.errors.registerFailed'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>{t('auth.register')}</h2>
      {error && <p style={errorStyle}>{error}</p>}
      <label htmlFor="reg-username">{t('auth.usernameWithLimit', { max: 10 })}</label>
      <input
        type="text"
        id="reg-username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        maxLength="10"
        required
        style={inputStyle}
      />
      <label htmlFor="reg-name">{t('auth.nameWithLimit', { max: 40 })}</label>
      <input
        type="text"
        id="reg-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength="40"
        required
        style={inputStyle}
      />
      <label htmlFor="reg-password">{t('auth.passwordWithLimit', { min: 10, max: 20 })}</label>
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
      <label htmlFor="reg-confirm-password">{t('auth.confirmPassword')}</label>
      <input
        type="password"
        id="reg-confirm-password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        required
        style={inputStyle}
      />
      <button type="submit" disabled={loading} style={buttonStyle}>
        {loading ? t('auth.registering') : t('auth.registerButton')}
      </button>
    </form>
  );
}

export default RegisterForm; 