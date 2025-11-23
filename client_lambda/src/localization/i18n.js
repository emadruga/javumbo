import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import enTranslation from './en/translation.json';
import ptTranslation from './pt/translation.json';
import esTranslation from './es/translation.json';

// Configure i18next
i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Set up i18next
  .init({
    debug: process.env.NODE_ENV === 'development',
    fallbackLng: 'pt',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    resources: {
      en: {
        translation: enTranslation
      },
      pt: {
        translation: ptTranslation
      },
      es: {
        translation: esTranslation
      }
    },
    detection: {
      // Order of detection methods
      order: ['localStorage', 'navigator'],
      // Look for language in localStorage
      lookupLocalStorage: 'i18nextLng',
      // Cache user language
      caches: ['localStorage'],
    },
    // Force Portuguese as initial language
    lng: 'pt'
  });

export default i18n; 