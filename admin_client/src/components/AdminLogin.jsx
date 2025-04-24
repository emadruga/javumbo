import React, { useState } from 'react';

function AdminLogin({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null); // State for error messages
  const [isLoading, setIsLoading] = useState(false); // State for loading indicator

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true); // Start loading
    setError(null); // Clear previous errors
    console.log('Admin Login attempt:', { username }); // Log attempt (without password)

    // Define API URL (make this configurable later if needed)
    const apiUrl = 'http://localhost:9000/admin/login';

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) { // Check if response status is 200-299
        const data = await response.json();
        console.log('Admin Login Successful:', data);
        onLoginSuccess(); // Call the function passed from App.jsx
      } else {
        // Handle specific errors based on status code
        let errorMessage = `Login failed (Status: ${response.status})`;
        try {
            const errorData = await response.json();
            errorMessage = errorData.error || errorMessage; // Use server error message if available
        } catch { // Omit the error parameter
            // If parsing error response fails, use the status text
            errorMessage = response.statusText || errorMessage;
        }
        console.error('Login Error:', errorMessage);
        setError(errorMessage);
        // alert(errorMessage); // Use state for error display instead of alert
      }
    } catch (networkError) {
      // Handle network errors (e.g., server down)
      console.error('Network Error during login:', networkError);
      const errMsg = 'Could not connect to the server. Please try again later.';
      setError(errMsg);
      // alert(errMsg);
    } finally {
        setIsLoading(false); // Stop loading regardless of outcome
    }

    /* Remove placeholder logic:
    if (username === 'admin' && password === 'password') { 
      console.log('Admin Login Successful (Placeholder)');
      onLoginSuccess(); 
    } else {
      alert('Invalid credentials (Placeholder)');
    }
    */
  };

  return (
    <div>
      <h2>Admin Login</h2>
      <form onSubmit={handleSubmit}>
        {/* Display Error Message */}
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <div>
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={isLoading} // Disable input while loading
          />
        </div>
        <div>
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isLoading} // Disable input while loading
          />
        </div>
        {/* Disable button and show loading text */}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

export default AdminLogin; 