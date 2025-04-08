import React, { useState/* , useEffect */ } from 'react'; // Comment out useEffect
import { Routes, Route, useNavigate/* , useLocation */ } from 'react-router-dom'; // Comment out useLocation
import AuthPage from './pages/AuthPage.jsx';
import ReviewPage from './components/ReviewPage.jsx'; // Uncomment
import AddCardPage from './components/AddCardPage.jsx'; // Uncomment
import DecksPage from './pages/DecksPage.jsx'; // Uncomment
import DeckStatisticsPage from './components/DeckStatisticsPage.jsx'; // Import the new page
import api from './api/axiosConfig.js'; // Import configured Axios instance

function App() {
  // Restore state and hooks
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  // const location = useLocation(); // Comment out location hook usage

  // Restore handlers
  const handleLoginSuccess = (userData) => {
    console.log("App.jsx: Login successful:", userData);
    setUser(userData);
    navigate('/decks'); // Restore navigation to decks
    // navigate('/'); // Navigate to root after login for testing
  };

  const handleLogout = async () => { // Uncomment
    console.log("App.jsx: Initiating logout...");
    try {
      await api.post('/logout');
      setUser(null);
      navigate('/'); 
      console.log("App.jsx: Logout successful");
    } catch (error) {
      console.error("App.jsx: Logout failed:", error);
      setUser(null);
      navigate('/');
    }
  };

  // Restore effect (optional: for checking session on load - keep commented for now)
  // useEffect(() => {
  //   // Check if user data exists (e.g., in localStorage or via a /check-session endpoint)
  //   // For simplicity, we assume if not logged in, user is null.
  //   // A real app might have a /check-session endpoint called here.
  //   // if (!user && location.pathname !== '/') {
  //   //    // If no user and not on auth page, redirect to auth
  //   //    // navigate('/');
  //   // }
  // }, [user, navigate, location.pathname]);

  console.log("Rendering App (Restored)...");

  return (
    <div className="App">
      {/* <h1>Testing - App Shell Rendered</h1> */}{/* Remove test heading */}
      <Routes>
        <Route 
            path="/"
            element={<AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
        <Route
            path="/decks"
            element={user ? <DecksPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
        <Route
           path="/review"
           element={user ? <ReviewPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
        <Route
           path="/add"
           element={user ? <AddCardPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
        <Route
           path="/decks/:deckId/stats"
           element={user ? <DeckStatisticsPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
      </Routes>
    </div>
  );
}

export default App;
