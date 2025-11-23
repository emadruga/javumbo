import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import RegisterForm from '../components/RegisterForm';

/**
 * LoginPage - JWT Authentication with AuthContext
 *
 * Uses AuthContext for centralized JWT management
 * Supports both Login and Register tabs
 */
const LoginPage = () => {
  const [activeTab, setActiveTab] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(username, password);

      if (result.success) {
        console.log(`[LoginPage] ✓ Login successful: ${username}`);
        // Redirect to decks page
        navigate('/decks');
      } else {
        setError(result.error);
      }

    } catch (err) {
      console.error('[LoginPage] Login failed:', err);
      setError('Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSuccess = () => {
    // Switch to login tab after successful registration
    setActiveTab('login');
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-md-6">
          <div className="card">
            <div className="card-body">
              {/* Tab Navigation */}
              <ul className="nav nav-tabs mb-4">
                <li className="nav-item">
                  <button
                    className={`nav-link ${activeTab === 'login' ? 'active' : ''}`}
                    onClick={() => setActiveTab('login')}
                  >
                    Login
                  </button>
                </li>
                <li className="nav-item">
                  <button
                    className={`nav-link ${activeTab === 'register' ? 'active' : ''}`}
                    onClick={() => setActiveTab('register')}
                  >
                    Register
                  </button>
                </li>
              </ul>

              {/* Tab Content */}
              {activeTab === 'login' ? (
                <>
                  <h2 className="card-title text-center mb-4">Login</h2>

                  {error && <div className="alert alert-danger">{error}</div>}

                  <form onSubmit={handleSubmit}>
                    <div className="mb-3">
                      <label htmlFor="username" className="form-label">
                        Username
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                      />
                    </div>

                    <div className="mb-3">
                      <label htmlFor="password" className="form-label">
                        Password
                      </label>
                      <input
                        type="password"
                        className="form-control"
                        id="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      className="btn btn-primary w-100"
                      disabled={loading}
                    >
                      {loading ? 'Logging in...' : 'Login'}
                    </button>
                  </form>

                  <div className="mt-3 text-center">
                    <small className="text-muted">
                      Test User: <code>test_user</code> / <code>password123</code>
                    </small>
                  </div>
                </>
              ) : (
                <RegisterForm onRegisterSuccess={handleRegisterSuccess} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
