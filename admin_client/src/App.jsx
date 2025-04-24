import { useState } from 'react'
// Remove default logos and css
// import reactLogo from './assets/react.svg'
// import viteLogo from '/vite.svg'
import './App.css'
import AdminLogin from './components/AdminLogin'; // Import the new component
import UserList from './components/UserList'; // Import the UserList component
import DeckList from './components/DeckList'; // Import the DeckList component
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  // Remove default state
  // const [count, setCount] = useState(0)

  // TODO: Add state to track admin authentication
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);

  const handleLoginSuccess = () => {
    setIsAdminAuthenticated(true);
    // No explicit navigation needed here, protected routes will become accessible
  };

  // Simple Protected Route Component (can be extracted later)
  function ProtectedRoute({ children }) {
    if (!isAdminAuthenticated) {
        // Redirect to login if not authenticated
        return <Navigate to="/login" replace />;
    }
    return children;
  }

  return (
    <BrowserRouter>
      <div>
        <h1>Admin Dashboard</h1> {/* Keep header outside routes? */} 
        <Routes>
          <Route 
            path="/login" 
            element={isAdminAuthenticated ? <Navigate to="/users" replace /> : <AdminLogin onLoginSuccess={handleLoginSuccess} />} 
          />
          <Route 
            path="/users" 
            element={
              <ProtectedRoute>
                <UserList />
              </ProtectedRoute>
            }
          />
          {/* Add route for DeckList later */}
          <Route 
            path="/users/:username/decks" 
            element={
              <ProtectedRoute>
                <DeckList />
              </ProtectedRoute>
            }
          />
          
          {/* Default route handler */}
          <Route 
            path="*" 
            element={isAdminAuthenticated ? <Navigate to="/users" replace /> : <Navigate to="/login" replace />}
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App
