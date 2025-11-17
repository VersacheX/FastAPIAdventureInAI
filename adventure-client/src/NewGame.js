import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from './config';

function NewGame({ token, username, onClose, onCreate }) {
  const [loading, setLoading] = useState(false);
  const [worlds, setWorlds] = useState([]);
  const [ratings, setRatings] = useState([]);
  const [error, setError] = useState('');
  
  const [playerName, setPlayerName] = useState('');
  const [selectedWorld, setSelectedWorld] = useState('');
  const [selectedRating, setSelectedRating] = useState('');
  const [selectedGender, setSelectedGender] = useState('');

  useEffect(() => {
    const fetchOptions = async () => {
      setLoading(true);
      setError('');
      try {
        const [worldsResp, ratingsResp] = await Promise.all([
          axios.get(`${API_URL}/worlds/`, {
            headers: { Authorization: `Bearer ${token}` }
          }),
          axios.get(`${API_URL}/game_ratings/`, {
            headers: { Authorization: `Bearer ${token}` }
          })
        ]);
        setWorlds(worldsResp.data || []);
        setRatings(ratingsResp.data || []);
        
        // Set defaults if available
        if (worldsResp.data?.length > 0) setSelectedWorld(worldsResp.data[0].id);
        if (ratingsResp.data?.length > 0) setSelectedRating(ratingsResp.data[0].id);
        setSelectedGender('male');
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Failed to load game options');
      } finally {
        setLoading(false);
      }
    };
    if (token) fetchOptions();
  }, [token]);

  const handleCreate = async () => {
    if (!playerName.trim()) {
      setError('Player name is required');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      // Get user ID
      const userResp = await axios.get(`${API_URL}/users/by_username/${username}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const userId = userResp.data.id;
      
      // Get the selected world's preface
      const selectedWorldData = worlds.find(w => w.id === parseInt(selectedWorld));
      const preface = selectedWorldData?.preface || '';
      
      // Create the saved game with initial preface history
      const createResp = await axios.post(
        `${API_URL}/saved_games/`,
        {
          user_id: userId,
          world_id: parseInt(selectedWorld),
          rating_id: parseInt(selectedRating),
          player_name: playerName.trim(),
          player_gender: selectedGender,
          history: preface ? [{ entry: preface }] : [],
          tokenized_history: null
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const newGameId = createResp.data.id;
      
      // Fetch the full game data
      const gameResp = await axios.get(`${API_URL}/saved_games/${newGameId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      onCreate(gameResp.data);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to create game');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h2>New Game</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">
          {error && <div className="login-error">{error}</div>}
          
          <div className="new-game-form">
            <div className="form-group">
              <label htmlFor="player-name">Player Name</label>
              <input
                id="player-name"
                type="text"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                placeholder="Enter your character name"
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="world">World</label>
              <select
                id="world"
                value={selectedWorld}
                onChange={(e) => setSelectedWorld(e.target.value)}
                disabled={loading}
              >
                {worlds.map(w => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="rating">Rating</label>
              <select
                id="rating"
                value={selectedRating}
                onChange={(e) => setSelectedRating(e.target.value)}
                disabled={loading}
              >
                {ratings.map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gender">Gender</label>
              <select
                id="gender"
                value={selectedGender}
                onChange={(e) => setSelectedGender(e.target.value)}
                disabled={loading}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div className="form-actions">
              <button className="btn-cancel" onClick={onClose} disabled={loading}>
                Cancel
              </button>
              <button className="btn-create" onClick={handleCreate} disabled={loading}>
                {loading ? 'Creating...' : 'Create Game'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NewGame;
