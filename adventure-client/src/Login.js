import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from './config';
import './App.css';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  // Try auto-login if a token+username were saved
  useEffect(() => {
    const tryAuto = async () => {
      const storedToken = localStorage.getItem('ai_token');
      const storedUsername = localStorage.getItem('ai_username');
      if (storedToken && storedUsername) {
        try {
          const resp = await axios.get(`${API_URL}/users/by_username/${storedUsername}`, {
            headers: { Authorization: `Bearer ${storedToken}` }
          });
          if (resp.status === 200) {
            onLogin(storedToken);
          } else {
            // Invalid, clear
            localStorage.removeItem('ai_token');
            localStorage.removeItem('ai_username');
          }
        } catch (err) {
          localStorage.removeItem('ai_token');
          localStorage.removeItem('ai_username');
        }
      }
    };
    tryAuto();
  }, [onLogin]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // OAuth2 token endpoint expects form-encoded data
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);
      const response = await axios.post(`${API_URL}/token`, params);
      const token = response.data.access_token;
      // Persist token + username for automatic login next time
      try {
        localStorage.setItem('ai_token', token);
        localStorage.setItem('ai_username', username);
      } catch (err) {
        // Don't block login if storage fails
        console.warn('Failed to persist session to localStorage', err);
      }
      onLogin(token);
    } catch (err) {
      // Normalize error to a string so React never tries to render an object directly
      const detail = err.response?.data?.detail ?? err.response?.data ?? err.message ?? 'Login failed';
      const message = typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2);
      setError(message);
    }
  };

  return (
    <div className="login-page">
      <header className="login-header">
        <div className="app-title">AI Adventure in Python</div>
      </header>

      <form className="login-card" onSubmit={handleSubmit} aria-label="Login form">
        <h2 className="login-heading">Sign in</h2>

        <label className="sr-only" htmlFor="username">Username</label>
        <input
          id="username"
          className="login-input"
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          required
        />

        <label className="sr-only" htmlFor="password">Password</label>
        <input
          id="password"
          className="login-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
        />

        <button className="login-button" type="submit">Log In</button>

        {error && (
          <pre className="login-error" role="alert">{error}</pre>
        )}
      </form>
    </div>
  );
}

export default Login;