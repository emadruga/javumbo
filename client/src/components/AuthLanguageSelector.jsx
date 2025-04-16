import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

const dropdownStyle = {
  position: 'relative',
  display: 'inline-block'
};

const buttonStyle = {
  padding: '8px 16px',
  backgroundColor: 'white',
  border: '1px solid #ccc',
  borderRadius: '4px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  color: '#333'
};

const menuStyle = {
  position: 'absolute',
  top: '100%',
  right: 0,
  marginTop: '4px',
  backgroundColor: 'white',
  border: '1px solid #ccc',
  borderRadius: '4px',
  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  zIndex: 1000,
  minWidth: '120px'
};

const menuItemStyle = {
  padding: '8px 16px',
  cursor: 'pointer',
  display: 'block',
  width: '100%',
  textAlign: 'left',
  border: 'none',
  backgroundColor: 'transparent',
  color: '#333'
};

const activeMenuItemStyle = {
  ...menuItemStyle,
  backgroundColor: '#f0f0f0',
  fontWeight: 'bold'
};

function AuthLanguageSelector() {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'pt', name: 'Português' },
    { code: 'es', name: 'Español' }
  ];

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getCurrentLanguage = () => {
    const current = languages.find(lang => lang.code === i18n.language) || languages[0];
    return current.name;
  };

  const changeLanguage = (code) => {
    i18n.changeLanguage(code);
    setIsOpen(false);
  };

  return (
    <div style={dropdownStyle} ref={dropdownRef}>
      <button 
        style={buttonStyle}
        onClick={() => setIsOpen(!isOpen)}
      >
        {getCurrentLanguage()}
        <span style={{ fontSize: '10px', marginLeft: '4px' }}>▼</span>
      </button>
      
      {isOpen && (
        <div style={menuStyle}>
          {languages.map(({ code, name }) => (
            <button
              key={code}
              style={i18n.language === code ? activeMenuItemStyle : menuItemStyle}
              onClick={() => changeLanguage(code)}
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default AuthLanguageSelector; 