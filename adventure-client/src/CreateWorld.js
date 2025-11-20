import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, AI_URL } from './config';

function CreateWorld({ token, onBack, onWorldCreated, worldToEdit = null}) {
  const [name, setName] = useState('');
  const [preface, setPreface] = useState('');
  const [worldTokens, setWorldTokens] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [creating, setCreating] = useState(false);
  const [tokenCount, setTokenCount] = useState(0);
  const [maxTokens, setMaxTokens] = useState(1000);
  // maxTokens is now a prop
  const isEditMode = !!worldToEdit;
 
  // Populate form when editing
  useEffect(() => {
    if (worldToEdit) {
      setName(worldToEdit.name || '');
      setPreface(worldToEdit.preface || '');
      setWorldTokens(worldToEdit.world_tokens || '');
    }
  }, [worldToEdit]);

  // Fetch account level settings to determine dynamic max world tokens
  useEffect(() => {
    if (!token) return;
    axios.get(`${API_URL}/users/account_level/me`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    .then(res => {
      const dynamicMax = res.data?.game_settings?.max_world_tokens;
      if (typeof dynamicMax === 'number' && dynamicMax > 0) {
        setMaxTokens(dynamicMax);
      }
    })
    .catch(err => {
      // eslint-disable-next-line
      console.warn('Could not load account level settings, retaining default maxTokens. Reason:', err.response?.data?.detail || err.message);
    });
  }, [token]);

  // Calculate token count whenever fields change (with debouncing)
  useEffect(() => {
    const combinedText = `${name} ${preface} ${worldTokens}`;
    if (!combinedText.trim()) {
      setTokenCount(0);
      return;
    }

    // Debounce: wait 500ms after user stops typing before counting tokens
    const timeoutId = setTimeout(async () => {
      try {
        // eslint-disable-next-line
        console.log('Sending text to token counter:', combinedText.length, 'characters');
        const response = await axios.post(
          `${AI_URL}/count_tokens/`,
          { text: combinedText },
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
        // eslint-disable-next-line
        console.log('Token count response:', response.data);
        setTokenCount(response.data.token_count || 0);
      } catch (err) {
        console.error('Failed to count tokens:', err);
        setErrorMessage('Failed to calculate token count. AI server may be offline.');
      }
    }, 500);

    // Cleanup: cancel the timeout if user types again before 500ms
    return () => clearTimeout(timeoutId);
  }, [name, preface, worldTokens]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setCreating(true);

    try {
      const payload = {
        name: name.trim(),
        preface: preface.trim(),
        world_tokens: worldTokens.trim()
      };

      let response;
      if (isEditMode) {
        response = await axios.patch(
          `${API_URL}/worlds/${worldToEdit.id}`,
          payload,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
        alert('World updated successfully!');
      } else {
        response = await axios.post(
          `${API_URL}/worlds/`,
          payload,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
        alert('World created successfully!');
        
        // Clear form only on create
        setName('');
        setPreface('');
        setWorldTokens('');
      }

      // Call parent callback if provided
      if (onWorldCreated) {
        onWorldCreated(response.data);
      }
    } catch (err) {
      console.error(`Failed to ${isEditMode ? 'update' : 'create'} world:`, err);
      setErrorMessage(err.response?.data?.detail || `Failed to ${isEditMode ? 'update' : 'create'} world. Please try again.`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card modal-card-wide">
        <div className="modal-header">
          <h2>{isEditMode ? 'Edit World' : 'Create New World'}</h2>
          <button className="modal-close" onClick={onBack} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">
          {errorMessage && (
            <div className="login-error">
              {errorMessage}
            </div>
          )}
          
          <div className={`token-counter ${tokenCount > maxTokens ? 'token-counter-error' : tokenCount > maxTokens * 0.9 ? 'token-counter-warning' : ''}`}>
            <strong>Token Count:</strong> {tokenCount} / {maxTokens}
            {tokenCount > maxTokens && <span className="token-error-text"> - Exceeds limit!</span>}
            {tokenCount > maxTokens * 0.9 && tokenCount <= maxTokens && <span className="token-warning-text"> - Approaching limit</span>}
          </div>

          <form className="create-world-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="world-name">World Name *</label>
            <input
              id="world-name"
              type="text"
              className="form-input"
              placeholder="Enter world name (e.g., Chrono Trigger Convergence)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={64}
              disabled={creating}
            />
            <small className="form-hint">Must be unique. Max 64 characters.</small>
          </div>

          <div className="form-group">
            <label htmlFor="world-preface">Story Preface *</label>
            <textarea
              id="world-preface"
              className="form-textarea"
              placeholder="Enter the opening scene that introduces players to your world..."
              value={preface}
              onChange={(e) => setPreface(e.target.value)}
              required
              rows={6}
              disabled={creating}
            />
            <small className="form-hint">This is the entry point to the adventure.</small>
          </div>

          <div className="form-group">
            <label htmlFor="world-tokens">World Tokens (Context) *</label>
            <textarea
              id="world-tokens"
              className="form-textarea"
              placeholder="Define the universe, lore, artifacts, and rules that shape this world..."
              value={worldTokens}
              onChange={(e) => setWorldTokens(e.target.value)}
              required
              rows={8}
              disabled={creating}
            />
            <small className="form-hint">
              Keep this concise but descriptive. This context is sent to the AI with every request.
              Recommended: ~300-500 tokens.
            </small>
          </div>

          <div className="form-actions">
            <button 
              type="submit" 
              className="btn-primary"
              disabled={creating || !name.trim() || !preface.trim() || !worldTokens.trim()}
            >
              {creating ? (isEditMode ? 'Updating...' : 'Creating...') : (isEditMode ? 'Update World' : 'Create World')}
            </button>
            <button 
              type="button" 
              className="btn-secondary"
              onClick={onBack}
              disabled={creating}
            >
              Cancel
            </button>
          </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default CreateWorld;
