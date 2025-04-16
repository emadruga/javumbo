import React from 'react';
import { useTranslation } from 'react-i18next';

function LanguageSelector() {
  const { t, i18n } = useTranslation();

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
  };

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'pt', name: 'Português' },
    { code: 'es', name: 'Español' }
  ];

  // Get current language name
  const getCurrentLanguage = () => {
    const current = languages.find(lang => lang.code === i18n.language) || languages[0];
    return current.name;
  };

  return (
    <div className="dropdown">
      <button 
        className="btn btn-outline-light dropdown-toggle" 
        type="button" 
        id="languageDropdown" 
        data-bs-toggle="dropdown" 
        aria-expanded="false"
      >
        {getCurrentLanguage()}
      </button>
      <ul className="dropdown-menu dropdown-menu-end" aria-labelledby="languageDropdown">
        {languages.map(({ code, name }) => (
          <li key={code}>
            <button 
              className={`dropdown-item ${i18n.language === code ? 'active' : ''}`}
              onClick={() => changeLanguage(code)}
            >
              {name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default LanguageSelector; 