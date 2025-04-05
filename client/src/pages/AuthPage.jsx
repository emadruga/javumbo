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

function AuthPage({ onLoginSuccess }) {
  // Restore state
  const [activeTab, setActiveTab] = useState('login'); // 'login' or 'register'

  console.log(`Rendering AuthPage - active tab: ${activeTab}`);

  return (
    // Restore layout
    <div style={{ maxWidth: '400px', margin: '50px auto', fontFamily: 'Arial, sans-serif' }}>
      <h1>Flashcard App</h1>
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