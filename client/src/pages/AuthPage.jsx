import React, { useState } from 'react';
// Uncomment LoginForm import
import LoginForm from '../components/LoginForm.jsx';
// Uncomment RegisterForm import
import RegisterForm from '../components/RegisterForm.jsx';

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

function AuthPage({ onLoginSuccess }) {
  // Restore state
  const [activeTab, setActiveTab] = useState('login'); // 'login' or 'register'

  console.log(`Rendering AuthPage - active tab: ${activeTab}`);

  return (
    // Restore layout
    <div style={{ maxWidth: '400px', margin: '50px auto', fontFamily: 'Arial, sans-serif' }}>
      {/* Update title to Javumbo with custom styles */}
      <h1 style={titleStyles}>Javumbo</h1>
      <div>
        {/* Restore tab buttons */}
        <button
          style={activeTab === 'login' ? activeTabStyles : inactiveTabStyles}
          onClick={() => setActiveTab('login')}
        >
          Login
        </button>
        <button
          style={activeTab === 'register' ? activeTabStyles : inactiveTabStyles}
          onClick={() => setActiveTab('register')}
        >
          Register
        </button>
      </div>
      <div style={formContainerStyles}>
        {/* Render placeholders instead of actual forms */}
        {activeTab === 'login' ? (
          <LoginForm onLoginSuccess={onLoginSuccess} />
        ) : (
          <RegisterForm onRegisterSuccess={() => setActiveTab('login')} />
        )}
      </div>
    </div>
  );
}

export default AuthPage; 