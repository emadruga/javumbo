import React, { useState/* , useEffect */ } from 'react'; // Comment out useEffect
import { Routes, Route, useNavigate/* , useLocation */ } from 'react-router-dom'; // Comment out useLocation
import AuthPage from './pages/AuthPage.jsx';
import ReviewPage from './pages/ReviewPage.jsx';
import AddCardPage from './pages/AddCardPage.jsx'; // Import the new page
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
    navigate('/review'); // Navigate to review page after login
  };

  const handleLogout = async () => {
    console.log("App.jsx: Initiating logout...");
    try {
      await api.post('/logout');
      setUser(null);
      navigate('/'); // Navigate back to auth page
      console.log("App.jsx: Logout successful");
    } catch (error) {
      console.error("App.jsx: Logout failed:", error);
      // Handle logout error (e.g., display message)
      // Force logout on client even if server fails?
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

  console.log("Rendering App with full routes including /add...");

  return (
    <div className="App">
      {/* <h1>Flashcard App Shell</h1> Removed testing title */}
      <Routes>
        <Route 
            path="/"
            element={<AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
        {/* Protect the review route */}
        <Route
          path="/review"
          element={user ? <ReviewPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
          // Consider a more robust protected route component later
        />
        {/* Add route for AddCardPage */}
        <Route
          path="/add"
          element={user ? <AddCardPage user={user} onLogout={handleLogout} /> : <AuthPage onLoginSuccess={handleLoginSuccess} />}
        />
         {/* Add a catch-all or Not Found route if needed */}
         {/* <Route path="*" element={<div>Page Not Found</div>} /> */}
      </Routes>
    </div>
  );
}

export default App;
