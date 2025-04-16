import React from 'react'
import ReactDOM from 'react-dom/client'
import 'bootstrap/dist/css/bootstrap.min.css'; // Add Bootstrap CSS import
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
// import './index.css' // Remove this line - file was deleted
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'; // Restore this import
import './localization/i18n.js'; // Import i18n configuration

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter> { /* Restore this wrapper */}
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
