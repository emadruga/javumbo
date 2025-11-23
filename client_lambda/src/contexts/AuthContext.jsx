import { createContext, useState, useContext, useEffect } from 'react';
import axios from '../api/axiosConfig';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize auth state from localStorage
  useEffect(() => {
    const storedToken = localStorage.getItem('jwt_token');
    const storedUsername = localStorage.getItem('username');

    if (storedToken && storedUsername) {
      setToken(storedToken);
      setUsername(storedUsername);
      // Set default Authorization header
      axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
    }

    setLoading(false);
  }, []);

  const login = async (username, password) => {
    try {
      // Call Lambda backend login endpoint
      const response = await axios.post('/login', { username, password });

      const { access_token } = response.data;

      // Store token and username
      setToken(access_token);
      setUsername(username);
      localStorage.setItem('jwt_token', access_token);
      localStorage.setItem('username', username);

      // Set default Authorization header for all future requests
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

      return { success: true };
    } catch (error) {
      console.error('Login failed:', error);
      return {
        success: false,
        error: error.response?.data?.error || 'Login failed'
      };
    }
  };

  const logout = () => {
    setToken(null);
    setUsername(null);
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('username');
    sessionStorage.removeItem('db_session_id');
    delete axios.defaults.headers.common['Authorization'];
  };

  const isAuthenticated = () => {
    return !!token;
  };

  const value = {
    token,
    username,
    login,
    logout,
    isAuthenticated,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
