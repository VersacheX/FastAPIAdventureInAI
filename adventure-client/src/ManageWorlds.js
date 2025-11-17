import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_URL } from './config';

function ManageWorlds({ token, onClose, onEditWorld }) {
  const [loading, setLoading] = useState(false);
  const [worlds, setWorlds] = useState([]);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const fetchWorlds = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API_URL}/users/me/worlds/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWorlds(response.data || []);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to load worlds');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) fetchWorlds();
  }, [token]);

  const handleEdit = (world) => {
    onEditWorld(world);
  };

  const handleDelete = (worldId, worldName) => {
    setDeleteConfirm({ id: worldId, name: worldName });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    
    try {
      await axios.delete(`${API_URL}/worlds/${deleteConfirm.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Refresh list
      await fetchWorlds();
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to delete world');
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
            <h3>Delete World?</h3>
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
        <div className="modal-card modal-card-scrollable">
          <div className="modal-header">
            <h2>Manage Worlds</h2>
            <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
          </div>
          <div className="modal-body">
            {loading && <div>Loading worlds…</div>}
            {error && <div className="login-error">{error}</div>}
            {!loading && !worlds.length && <div>No custom worlds found.</div>}
            <ul className="saved-games-list">
              {worlds.map(w => (
                <li key={w.id} className="saved-game-item">
                  <div className="saved-game-info">
                    <div className="saved-game-left">
                      <div className="saved-game-title">{w.name}</div>
                    </div>
                    <div className="saved-game-right">
                      <div className="saved-game-meta">
                        <div>{w.game_count} game{w.game_count !== 1 ? 's' : ''}</div>
                        <div>Created: {new Date(w.created_at).toLocaleDateString()}</div>
                        <div>Modified: {new Date(w.updated_at).toLocaleDateString()}</div>
                      </div>
                    </div>
                  </div>
                  <div className="saved-game-actions">
                    <button className="load-button" onClick={() => handleEdit(w)}>Edit</button>
                    <button className="delete-button" onClick={() => handleDelete(w.id, w.name)} aria-label="Delete world">🗑️</button>
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

export default ManageWorlds;
