import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from './config';

function LoadGame({ token, username, onClose, onLoad }) {
  const [loading, setLoading] = useState(false);
  const [games, setGames] = useState([]);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  useEffect(() => {
    const fetchGames = async () => {
      setLoading(true);
      setError('');
      try {
        // Get user by username to obtain id
        const userResp = await axios.get(`${API_URL}/users/by_username/${username}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const user = userResp.data;
        const listResp = await axios.get(`${API_URL}/users/${user.id}/saved_games/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setGames(listResp.data || []);
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Failed to load saved games');
      } finally {
        setLoading(false);
      }
    };
    if (token && username) fetchGames();
  }, [token, username]);

  const handleSelect = async (gameId) => {
    try {
      const resp = await axios.get(`${API_URL}/saved_games/${gameId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const fullGame = resp.data;
      onLoad(fullGame);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to load game');
    }
  };

  const handleDelete = (gameId, gameName) => {
    setDeleteConfirm({ id: gameId, name: gameName });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await axios.delete(`${API_URL}/saved_games/${deleteConfirm.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setGames(games.filter(g => g.id !== deleteConfirm.id));
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to delete game');
      setDeleteConfirm(null);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirm(null);
  };

  return (
    <>
      {deleteConfirm && (
        <div className="modal-backdrop" style={{ zIndex: 1001 }}>
          <div className="confirm-dialog">
            <h3>Delete Game?</h3>
            <p>Are you sure you want to delete <strong>{deleteConfirm.name}</strong>?</p>
            <p className="confirm-warning">This action cannot be undone.</p>
            <div className="confirm-actions">
              <button className="confirm-cancel" onClick={cancelDelete}>Cancel</button>
              <button className="confirm-delete" onClick={confirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
      <div className="modal-backdrop" role="dialog" aria-modal="true">
        <div className="modal-card">
        <div className="modal-header">
          <h2>Load Game</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">
          {loading && <div>Loading saved games…</div>}
          {error && <div className="login-error">{error}</div>}
          {!loading && !games.length && <div>No saved games found.</div>}
          <ul className="saved-games-list">
            {games.map(g => (
              <li key={g.id} className="saved-game-item">
                <div className="saved-game-info">
                  <div className="saved-game-left">
                    <div className="saved-game-title">{g.player_name} | {g.world_name}</div>
                  </div>
                  <div className="saved-game-right">
                    <div className="saved-game-meta">
                      {g.rating_name} • {g.history_count || 0} entries • {new Date(g.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <div className="saved-game-actions">
                  <button className="load-button" onClick={() => handleSelect(g.id)}>Load</button>
                  <button className="delete-button" onClick={() => handleDelete(g.id, g.player_name)} aria-label="Delete game">🗑️</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
    </>
  );
}

export default LoadGame;
