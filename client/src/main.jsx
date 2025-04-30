import React from 'react';
import ReactDOM from 'react-dom/client';
import 'bootstrap/dist/css/bootstrap.min.css'; // Add Bootstrap CSS import
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './localization/i18n.js'; // Import i18n configuration
// import './index.css' // Remove this line - file was deleted

// Access the environment variable (exposed via import.meta.env)
const appBasePath = import.meta.env.VITE_APP_BASE_PATH || '/';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={appBasePath}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
