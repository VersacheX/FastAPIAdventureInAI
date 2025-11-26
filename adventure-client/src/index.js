import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { BrowserRouter } from 'react-router-dom';
import axios from 'axios';

// Global axios interceptor: if any request returns401/403, clear saved credentials
// and navigate to the login route. This ensures a page refresh on a phone will
// force the user back to the login screen when their token is invalid/expired.
function handleGlobalLogout() {
  try {
    localStorage.removeItem('ai_token');
    localStorage.removeItem('ai_username');
    localStorage.removeItem('currentGameId');
  } catch (err) {
    // ignore
  }
  try {
    // Broadcast logout to other tabs/windows
    localStorage.setItem('ai_logout', Date.now().toString());
  } catch (err) {}
  // Redirect to root which shows the login screen when not authenticated
  window.location.href = '/';
}

axios.interceptors.response.use(
  response => response,
  error => {
    const status = error?.response?.status;
    if (status ===401 || status ===403) {
      handleGlobalLogout();
    }
    return Promise.reject(error);
  }
);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
