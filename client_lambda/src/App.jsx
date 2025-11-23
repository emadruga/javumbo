import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import ReviewPage from './pages/ReviewPage';
import DecksPage from './pages/DecksPage';
import AddCardPage from './pages/AddCardPage';
import EditCardPage from './pages/EditCardPage';
import DeckStatisticsPage from './pages/DeckStatisticsPage';

/**
 * Protected Route Wrapper
 * Redirects to /login if user is not authenticated
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>;
  }

  return isAuthenticated() ? children : <Navigate to="/login" replace />;
}

/**
 * App Routes Component
 * Must be inside AuthProvider to access auth context
 */
function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={
          isAuthenticated() ? <Navigate to="/decks" replace /> : <LoginPage />
        }
      />

      {/* Protected routes */}
      <Route
        path="/decks"
        element={
          <ProtectedRoute>
            <DecksPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/review"
        element={
          <ProtectedRoute>
            <ReviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/add"
        element={
          <ProtectedRoute>
            <AddCardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/edit/:cardId"
        element={
          <ProtectedRoute>
            <EditCardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/decks/:deckId/stats"
        element={
          <ProtectedRoute>
            <DeckStatisticsPage />
          </ProtectedRoute>
        }
      />

      {/* Default redirect */}
      <Route
        path="*"
        element={<Navigate to={isAuthenticated() ? "/decks" : "/login"} replace />}
      />
    </Routes>
  );
}

/**
 * Main App Component
 * Wraps entire app in AuthProvider for JWT management
 */
const App = () => {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
};

export default App;
