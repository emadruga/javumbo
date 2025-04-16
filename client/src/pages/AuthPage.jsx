import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LoginForm from '../components/LoginForm.jsx';
import RegisterForm from '../components/RegisterForm.jsx';
import AuthLanguageSelector from '../components/AuthLanguageSelector';

// Restore styles
const tabStyles = {
  padding: '10px 15px',
  cursor: 'pointer',
  border: '1px solid #ccc',
  borderBottom: 'none',
  marginRight: '5px',
  borderRadius: '5px 5px 0 0',
};
const activeTabStyles = {
  ...tabStyles,
  backgroundColor: '#eee',
  borderBottom: '1px solid #eee',
};
const inactiveTabStyles = {
  ...tabStyles,
  backgroundColor: '#f9f9f9',
};
const formContainerStyles = {
  border: '1px solid #ccc',
  padding: '20px',
  borderRadius: '0 5px 5px 5px',
  marginTop: '-1px' // Align border with tab bottom
};

// Add custom title styles
const titleStyles = {
  fontFamily: "'Montserrat', sans-serif",
  fontSize: '42px',
  fontWeight: '700',
  color: '#4a6eb5',
  textAlign: 'center',
  margin: '20px 0',
  textShadow: '2px 2px 4px rgba(0, 0, 0, 0.1)',
  letterSpacing: '1px',
  background: 'linear-gradient(45deg, #4a6eb5, #7a54a8)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  padding: '10px 0'
};

const languageSelectorContainerStyle = {
  position: 'absolute',
  top: '20px',
  right: '20px'
};

function AuthPage({ onLoginSuccess }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('login');

  console.log(`Rendering AuthPage - active tab: ${activeTab}`);

  return (
    <div style={{ position: 'relative', minHeight: '100vh' }}>
      <div style={languageSelectorContainerStyle}>
        <AuthLanguageSelector />
      </div>
      <div style={{ maxWidth: '400px', margin: '50px auto', fontFamily: 'Arial, sans-serif' }}>
        <h1 style={titleStyles}>{t('app.title')}</h1>
        <div>
          <button
            style={activeTab === 'login' ? activeTabStyles : inactiveTabStyles}
            onClick={() => setActiveTab('login')}
          >
            {t('auth.login')}
          </button>
          <button
            style={activeTab === 'register' ? activeTabStyles : inactiveTabStyles}
            onClick={() => setActiveTab('register')}
          >
            {t('auth.register')}
          </button>
        </div>
        <div style={formContainerStyles}>
          {activeTab === 'login' ? (
            <LoginForm onLoginSuccess={onLoginSuccess} />
          ) : (
            <RegisterForm onRegisterSuccess={() => setActiveTab('login')} />
          )}
        </div>
      </div>
    </div>
  );
}

export default AuthPage;