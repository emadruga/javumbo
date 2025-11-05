import axios from 'axios';

// Access the environment variable
// Default to empty string for production (uses relative URLs through nginx proxy)
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL !== undefined
  ? import.meta.env.VITE_API_BASE_URL
  : 'http://localhost:8000';

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