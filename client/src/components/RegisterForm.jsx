import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../api/axiosConfig';

const inputStyle = {
  display: 'block',
  width: 'calc(100% - 20px)',
  padding: '8px',
  marginBottom: '10px',
  border: '1px solid #ccc',
  borderRadius: '4px'
};

const selectStyle = {
  ...inputStyle,
  backgroundColor: 'white'
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
  const [formData, setFormData] = useState({
    username: '',
    name: '',
    email: '',
    groupCode: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Basic frontend validation
    if (!formData.username || !formData.name || !formData.password || 
        !formData.confirmPassword || !formData.email || !formData.groupCode) {
      setError(t('auth.errors.required'));
      return;
    }

    if (formData.username.length > 10) {
      setError(t('auth.errors.usernameLength', { max: 10 }));
      return;
    }

    if (formData.name.length > 40) {
      setError(t('auth.errors.nameLength', { max: 40 }));
      return;
    }

    if (formData.password.length < 10 || formData.password.length > 20) {
      setError(t('auth.errors.passwordLength', { min: 10, max: 20 }));
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError(t('auth.errors.passwordMatch'));
      return;
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError(t('auth.errors.invalidEmail'));
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/register', {
        username: formData.username,
        name: formData.name,
        email: formData.email,
        group_code: formData.groupCode,
        password: formData.password,
      });
      
      console.log('Registration successful:', response.data);
      alert(t('auth.successRegister'));
      
      if (onRegisterSuccess) {
        onRegisterSuccess();
      }
      
      // Clear form
      setFormData({
        username: '',
        name: '',
        email: '',
        groupCode: '',
        password: '',
        confirmPassword: ''
      });

    } catch (err) {
      console.error('Registration error:', err);
      if (err.response?.data?.error) {
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
        name="username"
        value={formData.username}
        onChange={handleChange}
        maxLength="10"
        required
        style={inputStyle}
        placeholder={t('auth.usernamePlaceholder')}
        title={t('auth.errors.required')}
      />

      <label htmlFor="reg-name">{t('auth.nameWithLimit', { max: 40 })}</label>
      <input
        type="text"
        id="reg-name"
        name="name"
        value={formData.name}
        onChange={handleChange}
        maxLength="40"
        required
        style={inputStyle}
        placeholder={t('auth.namePlaceholder')}
        title={t('auth.errors.required')}
      />

      <label htmlFor="reg-email">{t('auth.email')}</label>
      <input
        type="email"
        id="reg-email"
        name="email"
        value={formData.email}
        onChange={handleChange}
        required
        style={inputStyle}
        placeholder={t('auth.emailPlaceholder')}
        title={t('auth.errors.required')}
      />

      <label htmlFor="reg-group">{t('auth.groupCode')}</label>
      <select
        id="reg-group"
        name="groupCode"
        value={formData.groupCode}
        onChange={handleChange}
        required
        style={selectStyle}
      >
        <option value="">{t('auth.groupCodePlaceholder')}</option>
        <option value="30">{t('auth.groups.group30')}</option>
        <option value="40">{t('auth.groups.group40')}</option>
        <option value="50">{t('auth.groups.group50')}</option>
        <option value="255">{t('auth.groups.group255')}</option>
      </select>

      <label htmlFor="reg-password">{t('auth.passwordWithLimit', { min: 10, max: 20 })}</label>
      <input
        type="password"
        id="reg-password"
        name="password"
        value={formData.password}
        onChange={handleChange}
        minLength="10"
        maxLength="20"
        required
        style={inputStyle}
        placeholder={t('auth.passwordPlaceholder')}
        title={t('auth.errors.required')}
      />

      <label htmlFor="reg-confirm-password">{t('auth.confirmPassword')}</label>
      <input
        type="password"
        id="reg-confirm-password"
        name="confirmPassword"
        value={formData.confirmPassword}
        onChange={handleChange}
        required
        style={inputStyle}
        placeholder={t('auth.confirmPasswordPlaceholder')}
        title={t('auth.errors.required')}
      />

      <button 
        type="submit" 
        disabled={loading} 
        style={{...buttonStyle, marginRight: '10px'}}
      >
        {loading ? t('auth.registering') : t('auth.registerButton')}
      </button>
    </form>
  );
}

export default RegisterForm; 