import { useState } from 'react';
import { register } from '../api.js';

/**
 * RegisterForm - User registration component
 *
 * Simplified version for Lambda backend (no email/group_code)
 * Backend expects: username, name, password
 */
const RegisterForm = ({ onRegisterSuccess }) => {
  const [formData, setFormData] = useState({
    username: '',
    name: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Frontend validation
    if (!formData.username || !formData.name || !formData.password || !formData.confirmPassword) {
      setError('All fields are required');
      return;
    }

    if (formData.username.length < 1 || formData.username.length > 20) {
      setError('Username must be between 1 and 20 characters');
      return;
    }

    if (formData.name.length < 1 || formData.name.length > 50) {
      setError('Name must be between 1 and 50 characters');
      return;
    }

    if (formData.password.length < 10) {
      setError('Password must be at least 10 characters');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await register({
        username: formData.username,
        name: formData.name,
        password: formData.password,
      });

      console.log('[RegisterForm] Registration successful');
      alert('Registration successful! Please log in with your new account.');

      if (onRegisterSuccess) {
        onRegisterSuccess();
      }

      // Clear form
      setFormData({
        username: '',
        name: '',
        password: '',
        confirmPassword: ''
      });

    } catch (err) {
      console.error('[RegisterForm] Registration error:', err);
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2 className="text-center mb-4">Register</h2>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="mb-3">
        <label htmlFor="reg-username" className="form-label">
          Username (1-20 characters)
        </label>
        <input
          type="text"
          className="form-control"
          id="reg-username"
          name="username"
          value={formData.username}
          onChange={handleChange}
          maxLength="20"
          required
        />
      </div>

      <div className="mb-3">
        <label htmlFor="reg-name" className="form-label">
          Full Name (1-50 characters)
        </label>
        <input
          type="text"
          className="form-control"
          id="reg-name"
          name="name"
          value={formData.name}
          onChange={handleChange}
          maxLength="50"
          required
        />
      </div>

      <div className="mb-3">
        <label htmlFor="reg-password" className="form-label">
          Password (min 10 characters)
        </label>
        <input
          type="password"
          className="form-control"
          id="reg-password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          minLength="10"
          required
        />
      </div>

      <div className="mb-3">
        <label htmlFor="reg-confirm-password" className="form-label">
          Confirm Password
        </label>
        <input
          type="password"
          className="form-control"
          id="reg-confirm-password"
          name="confirmPassword"
          value={formData.confirmPassword}
          onChange={handleChange}
          required
        />
      </div>

      <button
        type="submit"
        className="btn btn-primary w-100"
        disabled={loading}
      >
        {loading ? 'Registering...' : 'Register'}
      </button>
    </form>
  );
};

export default RegisterForm;
