import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

// Basic inline styles (consider moving to CSS)
const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '1rem 0',
  borderBottom: '1px solid #eee',
  marginBottom: '1rem'
};

const navStyle = {
  display: 'flex',
  gap: '1rem'
};

const userInfoStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '1rem'
};

function Header({ user, onLogout }) {
  const navigate = useNavigate();

  const handleLogoutClick = (e) => {
    e.preventDefault();
    if (typeof onLogout === 'function') {
        onLogout();
    } else {
        console.error("onLogout prop is not a function or not provided");
        // Fallback navigation if needed
        // navigate('/'); 
    }
  };

  return (
    <header style={headerStyle}>
      <nav style={navStyle}>
        <Link to="/decks">Decks</Link>
        <Link to="/add">Add Card</Link>
        {/* Review link might be less common in header, often accessed via deck */}
        {/* <Link to="/review">Review</Link> */}
      </nav>
      {user && (
        <div style={userInfoStyle}>
          <span>Welcome, {user.name || user.username}!</span>
          <button onClick={handleLogoutClick} className="btn btn-outline-secondary btn-sm">
            Logout
          </button>
        </div>
      )}
    </header>
  );
}

export default Header; 