import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_URL } from './config';
import Login from './Login';
import LoadGame from './LoadGame';
import NewGame from './NewGame';
import CreateWorld from './CreateWorld';
import ManageWorlds from './ManageWorlds';
import Game from './Game';
import './App.css';
import { Routes, Route, useNavigate } from 'react-router-dom';

function App() {
 const [token, setToken] = useState(null);
 const [username, setUsername] = useState(null);
 const [menuOpen, setMenuOpen] = useState(false);
 const [loadOpen, setLoadOpen] = useState(false);
 const [newGameOpen, setNewGameOpen] = useState(false);
 const [createWorldOpen, setCreateWorldOpen] = useState(false);
 const [manageWorldsOpen, setManageWorldsOpen] = useState(false);
 const [worldToEdit, setWorldToEdit] = useState(null);
 const [currentGame, setCurrentGame] = useState(null);
 const [loading, setLoading] = useState(true);
 const [userGames, setUserGames] = useState([]);
 const [userWorlds, setUserWorlds] = useState([]);
 const [worldsToShow, setWorldsToShow] = useState(10);
 const [worldsError, setWorldsError] = useState('');
 const navigate = useNavigate();

 useEffect(() => {
 if (token) {
 setWorldsError('');
 axios.get(`${API_URL}/users/me/worlds/`, {
 headers: { Authorization: `Bearer ${token}` }
 })
 .then(res => {
 setUserWorlds(res.data || []);
 })
 .catch(err => {
 setWorldsError(err.response?.data?.detail ?? err.message ?? 'Failed to load worlds');
 });
 }
 // else {
 // handleLogout()
 // }
 }, [token]);

 useEffect(() => {
 const stored = localStorage.getItem('ai_token');
 const storedUser = localStorage.getItem('ai_username');
 if (stored) {
 setToken(stored);
 if (storedUser) setUsername(storedUser);
 }
 // Check for currentGameId in localStorage (set by Game.js)
 const storedGameId = localStorage.getItem('currentGameId');
 if (storedGameId && stored) {
 axios.get(`${API_URL}/saved_games/${storedGameId}`, {
 headers: { Authorization: `Bearer ${stored}` }
 })
 .then(response => {
 setCurrentGame(response.data);
 setLoading(false);
 })
 .catch(err => {
 console.error('Failed to reload game', err);
 localStorage.removeItem('currentGameId');
 setLoading(false);
 });
 } else {
 setLoading(false);
 }

 // Listen for cross-tab logout broadcasts
 function onStorage(e) {
 if (e.key === 'ai_logout') {
 // Clear local state and navigate to login
 setToken(null);
 setUsername(null);
 setCurrentGame(null);
 navigate('/');
 }
 }
 window.addEventListener('storage', onStorage);
 return () => window.removeEventListener('storage', onStorage);
 }, [navigate]);

 useEffect(() => {
 if (token && username) {
 axios.get(`${API_URL}/users/by_username/${username}`, {
 headers: { Authorization: `Bearer ${token}` }
 }).then(userRes => {
 const userId = userRes.data.id;
 axios.get(`${API_URL}/users/${userId}/saved_games/`, {
 headers: { Authorization: `Bearer ${token}` }
 }).then(gamesRes => {
 // Sort games by updated_at descending
 const sortedGames = gamesRes.data.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
 setUserGames(sortedGames);
 });
 });
 }
 }, [token, username]);

 const handleLogin = (newToken) => {
 setToken(newToken);
 const storedUser = localStorage.getItem('ai_username');
 if (storedUser) setUsername(storedUser);
 navigate('/');
 };

 const handleLogout = useCallback(() => {
 try { localStorage.removeItem('ai_token'); } catch (err) {}
 try { localStorage.removeItem('ai_username'); } catch (err) {}
 try { localStorage.removeItem('currentGameId'); } catch (err) {}
 setToken(null);
 setUsername(null);
 setMenuOpen(false);
 setCurrentGame(null);
 try { localStorage.setItem('ai_logout', Date.now().toString()); } catch (err) {}
 navigate('/');
 }, [navigate]);

 useEffect(() => {
     // Global axios response interceptor: logout on401 (expired/invalid token)
     const interceptor = axios.interceptors.response.use(
         res => res,
         err => {
             if (err.response && err.response.status ===401) {
                handleLogout();
             }
             return Promise.reject(err);
         }
     );
     return () => axios.interceptors.response.eject(interceptor);
 }, [handleLogout]);

 const handleGameLoaded = (game) => {
 if (game) {
 setCurrentGame(game);
 localStorage.setItem('currentGameId', game.id);
 navigate('/game');
 }
 };

 const handleExitGame = () => {
 setCurrentGame(null);
 try {
 localStorage.removeItem('currentGameId');
 } catch (err) {}
 navigate('/');
 };

 return (
 <div className="App-root">
 {loading ? (
 <div className="center-box">
 <div style={{color: '#fff', fontSize: '1.2rem'}}>Loading...</div>
 </div>
 ) : !token ? (
 <div className="center-box">
 <Login onLogin={handleLogin} />
 </div>
 ) : (
 <Routes>
 <Route path="/" element={
 <div>
 <header className="app-header">
 <div className="app-title">
 AI Adventure in Python
 {username && <span className="app-username">&nbsp;|&nbsp;{username}</span>}
 </div>
 <nav className={`app-menu ${menuOpen ? 'open' : ''}`}>
 {/* Removed New Game and Load Game buttons */}
 <button onClick={() => setCreateWorldOpen(true)}>Create World</button>
 <button onClick={() => setManageWorldsOpen(true)}>Manage Worlds</button>
 <button onClick={handleLogout}>Log Out</button>
 </nav>
 </header>
 <main className="app-main main-bg">
 <div className="home-blank">
 <div className="games-list-panel wide">
 <div className="games-list-header">
 <span className="games-list-title">Saved Games</span>
 <button className="new-game-list-btn" onClick={() => setNewGameOpen(true)}>+</button>
 </div>
 <ul className="games-list">
 {userGames.length ===0 ? (
 <li className="games-list-empty">No saved games yet.</li>
 ) : (
 userGames.slice(0,10).map(game => (
 <li key={game.id} className="games-list-item">
 <div className="games-list-row-flex">
 <button className="games-list-game-btn" onClick={async () => {
 try {
 const res = await axios.get(`${API_URL}/saved_games/${game.id}`, {
 headers: { Authorization: `Bearer ${token}` }
 });
 handleGameLoaded(res.data);
 } catch (err) {
 alert('Failed to load game.');
 }
 }}>
 <div className="games-list-title-row games-list-title-row-vertical">
 <div className="games-list-title-left">
 <div className="games-list-title-main">{game.player_name}</div>
 <div className="games-list-label games-list-world-name">{game.world_name}</div>
 </div>
 <div className="games-list-title-right games-list-details-right-vertical">
 <div className="games-list-label">{game.rating_name}</div>
 <div className="games-list-label">Entries: <span>{game.history_count}</span></div>
 </div>
 </div>
 <div className="games-list-date">Last played: {new Date(game.updated_at).toLocaleString()}</div>
 </button>
 <button className="games-list-trash-btn" title="Delete saved game" onClick={async (e) => {
 e.stopPropagation();
 if (window.confirm(`Are you sure you want to delete the game '${game.player_name}'? This cannot be undone.`)) {
 try {
 await axios.delete(`${API_URL}/saved_games/${game.id}`, {
 headers: { Authorization: `Bearer ${token}` }
 });
 setUserGames(userGames.filter(g => g.id !== game.id));
 } catch (err) {
 alert('Failed to delete game.');
 }
 }
 }}>
 🗑️
 </button>
 </div>
 </li>
 ))
 )}
 {userGames.length >10 && (
 <li className="games-list-item games-list-more">
 <button className="games-list-game-btn" onClick={() => setLoadOpen(true)}>
 Load more...
 </button>
 </li>
 )}
 </ul>
 </div>
 <div className="games-list-panel wide" style={{marginTop:32}}>
 <div className="games-list-header">
 <span className="games-list-title">Saved Worlds</span>
 <button className="new-game-list-btn" onClick={() => { setWorldToEdit(null); setCreateWorldOpen(true); }}>+</button>
 </div>
 {worldsError && (
 <div style={{padding: '16px', color: '#d04848'}}>{worldsError}</div>
 )}
 <ul className="saved-games-list" style={{maxHeight: '400px', overflowY: 'auto'}}>
 {userWorlds.length ===0 ? (
 <li className="games-list-empty">No custom worlds found.</li>
 ) : (
 userWorlds
 .slice()
 .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
 .slice(0, worldsToShow)
 .map(w => (
 <li key={w.id} className="saved-game-item" onClick={() => { setWorldToEdit(w); setCreateWorldOpen(true); }} style={{cursor: 'pointer'}}>
 <div className="saved-game-info">
 <div className="saved-game-left">
 <div className="saved-game-title">{w.name}</div>
 <div className="saved-game-meta" style={{ color: '#0ea5a4', fontWeight:500 }}>
 <div className="games-list-date">Last Mod: {new Date(w.updated_at).toLocaleDateString()}</div>
 </div>
 </div>
 <div className="saved-game-right">
 <div className="saved-game-meta">
 <div className="games-list-label">{w.game_count} game{w.game_count !==1 ? 's' : ''}</div> 
 {typeof w.token_count === 'number' && (
 <div className="games-list-label">{w.token_count} tokens</div>
 )}
 <div className="games-list-label">{new Date(w.created_at).toLocaleDateString()}</div>
 </div>
 </div>
 </div>
 <div className="saved-game-actions">
 <button className="games-list-trash-btn" onClick={async (e) => {
 e.stopPropagation();
 if (window.confirm(`Are you sure you want to delete the world '${w.name}'? This cannot be undone.`)) {
 try {
 await axios.delete(`${API_URL}/worlds/${w.id}`, {
 headers: { Authorization: `Bearer ${token}` }
 });
 setUserWorlds(userWorlds.filter(uw => uw.id !== w.id));
 } catch (err) {
 alert('Failed to delete world.');
 }
 }
 }} aria-label="Delete world">🗑️</button>
 </div>
 </li>
 ))
 )}
 {userWorlds.length > worldsToShow && (
 <li className="games-list-item games-list-more">
 <button className="games-list-game-btn" onClick={() => setWorldsToShow(worldsToShow +10)}>
 Load more...
 </button>
 </li>
 )}
 </ul>
 </div>
 </div>
 </main>
 {loadOpen && (
 <LoadGame
 token={token}
 username={username}
 onClose={() => setLoadOpen(false)}
 onLoad={handleGameLoaded}
 />
 )}
 {newGameOpen && (
 <NewGame
 token={token}
 username={username}
 onClose={() => setNewGameOpen(false)}
 onCreate={handleGameLoaded}
 />
 )}
 {createWorldOpen && (
 <CreateWorld
 token={token}
 worldToEdit={worldToEdit}
 onBack={() => {
 setCreateWorldOpen(false);
 setWorldToEdit(null);
 }}
 onWorldCreated={() => {
 setCreateWorldOpen(false);
 setWorldToEdit(null);
 }}
 />
 )}
 {manageWorldsOpen && (
 <ManageWorlds
 token={token}
 onClose={() => setManageWorldsOpen(false)}
 onEditWorld={setWorldToEdit}
 />
 )}
 </div>
 } />
 <Route path="/game" element={
 <Game game={currentGame} token={token} onExit={handleExitGame} onLogout={handleLogout} />
 } />
 </Routes>
 )}
 </div>
 );
}

export default App;
