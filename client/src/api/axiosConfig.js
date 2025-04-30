import axios from 'axios';

// Access the environment variable
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  // Use the environment variable for the baseURL
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

export default api;