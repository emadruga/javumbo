import React from 'react'
import ReactDOM from 'react-dom/client'
// import './index.css' // Remove this line - file was deleted
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'; // Restore this import

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter> { /* Restore this wrapper */}
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
