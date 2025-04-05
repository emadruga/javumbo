import React from 'react';
import { Link, useLocation } from 'react-router-dom';

// Basic styling (consider moving to CSS)
const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '10px 20px', // Added horizontal padding
  borderBottom: '1px solid #ccc',
  marginBottom: '20px',
  backgroundColor: '#f8f9fa' // Light background for header
};

const navLinksStyle = {
  display: 'flex',
  gap: '15px'
};

const linkStyle = {
  textDecoration: 'none',
  color: '#007bff',
  padding: '5px 0'
};

const activeLinkStyle = {
    ...linkStyle,
    fontWeight: 'bold',
    borderBottom: '2px solid #007bff'
};

const userInfoStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '15px'
};

const buttonStyle = {
    padding: '8px 15px',
    cursor: 'pointer',
    borderRadius: '4px',
    border: '1px solid #ccc'
};

const exportButtonStyle = {...buttonStyle, backgroundColor: '#6c757d', color: 'white'};
const logoutButtonStyle = {...buttonStyle, backgroundColor: '#ffc107', color: 'black'};

function Header({ user, onLogout, onExport, isExporting }) {
  const location = useLocation(); // Hook to check current path

  // Function to determine link style based on current path
  const getLinkStyle = (path) => {
    return location.pathname === path ? activeLinkStyle : linkStyle;
  };

  return (
    <header style={headerStyle}>
      <nav style={navLinksStyle}>
        <Link to="/review" style={getLinkStyle('/review')}>Review Cards</Link>
        <Link to="/add" style={getLinkStyle('/add')}>Add Card</Link>
      </nav>
      <div style={userInfoStyle}>
        {/* Conditionally render export button if handler is provided */}
        {onExport && (
            <button onClick={onExport} disabled={isExporting} style={exportButtonStyle}>
                {isExporting ? 'Exporting...' : 'Export Deck'}
            </button>
        )}
        <span>Welcome, {user?.name || 'User'}!</span>
        <button onClick={onLogout} style={logoutButtonStyle}>Logout</button>
      </div>
    </header>
  );
}

export default Header; 