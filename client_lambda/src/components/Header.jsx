import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';

function Header({ user, onLogout }) {
  const { t } = useTranslation();

  const handleLogoutClick = (e) => {
    e.preventDefault();
    if (typeof onLogout === 'function') {
      onLogout();
    } else {
      console.error("onLogout prop is not a function or not provided");
    }
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
      <div className="container">
        <Link className="navbar-brand" to="/decks">
          {t('app.title')}
        </Link>
        
        <button 
          className="navbar-toggler" 
          type="button" 
          data-bs-toggle="collapse" 
          data-bs-target="#navbarContent" 
          aria-controls="navbarContent" 
          aria-expanded="false" 
          aria-label={t('common.toggleNav')}
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        <div className="collapse navbar-collapse" id="navbarContent">
          <ul className="navbar-nav me-auto mb-2 mb-lg-0">
            <li className="nav-item">
              <Link className="nav-link" to="/decks">
                {t('decks.title')}
              </Link>
            </li>
            <li className="nav-item">
              <Link className="nav-link" to="/add">
                {t('cards.add')}
              </Link>
            </li>
          </ul>

          <div className="d-flex align-items-center">
            {user && (
              <>
                <span className="text-light me-3">
                  {t('common.welcome', { name: user.name || user.username })}
                </span>
                <LanguageSelector />
                <button 
                  onClick={handleLogoutClick} 
                  className="btn btn-outline-light ms-3"
                >
                  {t('decks.logout')}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Header; 