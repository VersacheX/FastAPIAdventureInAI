import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_URL, AI_URL } from './config';

function Game({ game, token, onExit, onLogout }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [tokenizedOpen, setTokenizedOpen] = useState(false);
  const [deepMemoryOpen, setDeepMemoryOpen] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [localHistory, setLocalHistory] = useState(game.history || []);
  const [localTokenized, setLocalTokenized] = useState(game.tokenized_history || []);
  const [deepMemory, setDeepMemory] = useState(null);
  const [tokenizedHistory, setTokenizedHistory] = useState([]);
  const [deepMemoryData, setDeepMemoryData] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editedText, setEditedText] = useState('');
  const [editingTokenizedId, setEditingTokenizedId] = useState(null);
  const [editedTokenizedSummary, setEditedTokenizedSummary] = useState('');
  const [editingDeepMemory, setEditingDeepMemory] = useState(false);
  const [editedDeepMemory, setEditedDeepMemory] = useState('');
  const [actionMode, setActionMode] = useState('ACTION');
  const [placeholderText, setPlaceholderText] = useState('Enter your action...');
  const [failedMessage, setFailedMessage] = useState(null);
  const [tokenStats, setTokenStats] = useState(null);
  const [mobileDetailsOpen, setMobileDetailsOpen] = useState(false);
  const [mobileTokenizedOpen, setMobileTokenizedOpen] = useState(false);
  const [mobileDeepMemoryOpen, setMobileDeepMemoryOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [playerAction, setPlayerAction] = useState('action'); // Example: 'action', 'say', 'story'
  const navigate = useNavigate();
  const scrollAreaRef = useRef(null);

  // Calculate token statistics locally from available data
  const calculateTokenStats = () => {
    const maxHistoryTokens = game.tokenize_threshold || 850;
    const maxTokenizedChunks = game.max_tokenized_history_block || 6;
    
    // Calculate active tokenized tokens (most recent chunks)
    const recentTokenized = localTokenized.slice(-maxTokenizedChunks);
    const activeTokenizedTokens = recentTokenized.reduce((sum, chunk) => sum + (chunk.token_count || 0), 0);
    
    // Calculate active history tokens (most recent entries up to threshold)
    // localHistory contains only untokenized entries
    let activeHistoryTokens = 0;
    let activeHistoryCount = 0;
    
    for (let i = localHistory.length - 1; i >= 0; i--) {
      const entryTokens = localHistory[i].token_count || 0;
      if (activeHistoryTokens + entryTokens <= maxHistoryTokens) {
        activeHistoryTokens += entryTokens;
        activeHistoryCount++;
      } else {
        break;
      }
    }
    
    // Calculate totals
    const activeTokens = activeTokenizedTokens + activeHistoryTokens;
    const totalTokens = localHistory.reduce((sum, h) => sum + (h.token_count || 0), 0);
    
    return {
      active_tokens: activeTokens,
      total_tokens: totalTokens,
      active_tokenized_chunks: recentTokenized.length,
      active_history_entries: activeHistoryCount,
      total_history_entries: localHistory.length
    };
  };

  // Update token stats whenever history or tokenized history changes
  useEffect(() => {
    const stats = calculateTokenStats();
    setTokenStats(stats);
  }, [localHistory, localTokenized, calculateTokenStats, setTokenStats ]);

  // Scroll to bottom whenever history changes
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [localHistory]);

  // Fetch tokenized history
  const fetchTokenizedHistory = async () => {
    try {
      const response = await axios.get(
        `${API_URL}/saved_games/${game.id}/tokenized_history/`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      setLocalTokenized(response.data);
      setTokenizedHistory(response.data); // Also update tokenizedHistory state
    } catch (err) {
      console.error('Failed to fetch tokenized history:', err);
    }
  };

  // Fetch deep memory
  const fetchDeepMemory = async () => {
    try {
      const response = await axios.get(
        `${API_URL}/saved_games/${game.id}/deep_memory/`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      setDeepMemory(response.data?.summary || null);
      setDeepMemoryData(response.data);
      console.log(`Deep Memory loaded: ${response.data?.chunks_merged || 0} chunks merged, ${response.data?.token_count || 0} tokens`);
    } catch (err) {
      // Deep memory doesn't exist yet - this is normal for new/short games
      if (err.response?.status === 404) {
        console.log('No deep memory yet (game history not long enough)');
        setDeepMemory(null);
        setDeepMemoryData(null);
      } else {
        console.error('Failed to fetch deep memory:', err);
      }
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchDeepMemory();
  }, []);

  const handleUndo = async () => {
    if (localHistory.length === 0 || submitting || generating) return;
    
    const lastEntry = localHistory[localHistory.length - 1];
    if (!lastEntry.id) return; // Can't delete if no ID
    
    try {
      // Delete from database
      await axios.delete(
        `${API_URL}/history/${lastEntry.id}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      // Remove from local state
      setLocalHistory(prev => prev.slice(0, -1));
      
      // Refresh tokenized history in case undo affected tokenization
      await fetchTokenizedHistory();
    } catch (err) {
      console.error('Failed to undo:', err);
      setErrorMessage('Failed to undo last entry.');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleEdit = (entry) => {
    setEditingId(entry.id);
    setEditedText(entry.entry || entry.text);
  };

  const handleSaveEdit = async (entryId) => {
    try {      
      const response = await axios.put(
        `${API_URL}/history/${entryId}`,
        { text: editedText },
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      console.log('Response:', response.data);
      
      // Update local state
      setLocalHistory(prev => prev.map(entry => 
        entry.id === entryId ? { ...entry, entry: editedText, text: editedText } : entry
      ));
      
      setEditingId(null);
      setEditedText('');
      
      // Refresh tokenized history in case editing affected tokenization
      await fetchTokenizedHistory();
    } catch (err) {
      console.error('Failed to save edit:', err);
      console.error('Error response:', err.response?.data);
      setErrorMessage('Failed to save changes.');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditedText('');
  };

  const handleEditTokenized = (block) => {
    setEditingTokenizedId(block.id);
    setEditedTokenizedSummary(block.summary);
  };

  const handleSaveTokenizedEdit = async (blockId) => {
    try {
      const response = await axios.put(
        `${API_URL}/tokenized_history/${blockId}`,
        { summary: editedTokenizedSummary },
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      // Update local state with the response data including recalculated token_count
      setLocalTokenized(prev => prev.map(block => 
        block.id === blockId ? response.data : block
      ));
      
      setEditingTokenizedId(null);
      setEditedTokenizedSummary('');
      
      // Token stats will auto-update via useEffect watching localTokenized
    } catch (err) {
      console.error('Failed to save tokenized edit:', err);
      setErrorMessage('Failed to save tokenized history changes.');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleCancelTokenizedEdit = () => {
    setEditingTokenizedId(null);
    setEditedTokenizedSummary('');
  };

  const handleEditDeepMemory = async () => {
    // If no deepMemoryData, create a new deep memory entry
    if (!deepMemoryData) {
      try {
        const response = await axios.post(`${API_URL}/deep_memory/`, {
          saved_game_id: game.id,
          summary: ''
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setDeepMemoryData(response.data);
        setDeepMemory('');
      } catch (err) {
        setErrorMessage('Failed to create deep memory.');
        setTimeout(() => setErrorMessage(''), 5000);
        return;
      }
    }
    setEditingDeepMemory(true);
    setEditedDeepMemory(deepMemory || '');
  };

  const handleSaveDeepMemoryEdit = async () => {
    try {
      let response;
      if (!deepMemoryData || !deepMemoryData.id) {
        // Create new deep memory if it doesn't exist or id is missing
        response = await axios.post(`${API_URL}/deep_memory/`, {
          saved_game_id: game.id,
          summary: editedDeepMemory
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      } else {
        // Update existing deep memory
        response = await axios.put(
          `${API_URL}/deep_memory/${deepMemoryData.id}`,
          { summary: editedDeepMemory },
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
      }
      setDeepMemory(response.data.summary);
      setDeepMemoryData(response.data);
      setEditingDeepMemory(false);
      setEditedDeepMemory('');
    } catch (err) {
      console.error('Failed to save deep memory edit:', err);
      setErrorMessage('Failed to save deep memory changes.');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleCancelDeepMemoryEdit = () => {
    setEditingDeepMemory(false);
    setEditedDeepMemory('');
  };

  const handleSubmit = async (e, retryInput = null) => {
    e?.preventDefault();
    if (submitting || generating) return;
    
    const currentInput = retryInput !== null ? retryInput : userInput.trim();
    if (retryInput === null) {
      setUserInput('');
    }
    setFailedMessage(null);
    setSubmitting(true);
    
    try {
      // Format the input based on action mode for saving to history
      let formattedInput = currentInput;
      if (currentInput) {
        if (actionMode === 'SPEECH') {
          formattedInput = `${game.player_name} says, "${currentInput}"`;
        }
        // ACTION and NARRATE modes save as-is
      }
      
      // Step 1: Save user's action to history via api.py (only if not empty)
      if (currentInput) {
        try {
          const userHistoryResponse = await axios.post(
            `${API_URL}/history/`,
            { entry: formattedInput },
            { 
              params: { saved_game_id: game.id },
              headers: { Authorization: `Bearer ${token}` } 
            }
          );
          
          // Update local history with user's entry
          const newUserEntry = userHistoryResponse.data;
          setLocalHistory(prev => [...prev, newUserEntry]);
        } catch (userSaveError) {
          console.error('Failed to save user action:', userSaveError);
          setUserInput(currentInput); // Restore user's input
          setErrorMessage('Failed to save your action. Please try again.');
          setTimeout(() => setErrorMessage(''), 5000);
          setSubmitting(false);
          return; // Exit early, don't proceed to AI generation
        }
      }
      
      setSubmitting(false);
      setGenerating(true);
      
      // Calculate which history to send to AI (use TOKENIZE_THRESHOLD from game settings)
      const maxHistoryTokens = game.tokenize_threshold || 850;
      let activeHistory = [];
      let tokenCount = 0;
      
      // Include current input if present
      const historyWithInput = formattedInput 
        ? [...localHistory, { entry: formattedInput, token_count: 0 }] 
        : [...localHistory];
      
      // Iterate backwards to get most recent entries up to tokenize_threshold tokens
      for (let i = historyWithInput.length - 1; i >= 0; i--) {
        const entry = historyWithInput[i];
        const entryTokens = entry.token_count || 0;
        if (tokenCount + entryTokens <= maxHistoryTokens) {
          activeHistory.unshift(entry);
          tokenCount += entryTokens;
        } else {
          break;
        }
      }
      
      // Get most recent tokenized chunks (use MAX_TOKENIZED_HISTORY_BLOCK from game settings)
      const maxTokenizedChunks = game.max_tokenized_history_block || 6;
      const activeTokenized = localTokenized.slice(-maxTokenizedChunks);
      
      // Step 2: Call AI server directly to generate response
      const requestData = {
        player_name: game.player_name,
        player_gender: game.player_gender,
        world_name: game.world_name,
        world_tokens: game.world_tokens || '',
        rating_name: game.rating_name,
        story_splitter: game.story_splitter || '###',
        story_preface: game.world_preface || '',
        history: activeHistory.map(h => h.entry || h.text),
        tokenized_history: activeTokenized.map(t => ({
          start_index: t.start_index,
          end_index: t.end_index,
          summary: t.summary,
          token_count: t.token_count
        })),
        deep_memory: deepMemory,
        user_input: currentInput,
        action_mode: 'ACTION', // Always use ACTION mode for retry
        include_initial: false
      };
      
      const aiResponse = await axios.post(
        `${AI_URL}/generate_from_game/`,
        requestData,
        {
          timeout: 120000, // 2 minutes timeout for AI generation
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      const aiStory = aiResponse.data.story;
      
      // Check if AI returned nothing
      if (!aiStory || !aiStory.trim()) {
        setErrorMessage('AI failed to generate a response. Click the blue message to retry.');
        setFailedMessage(''); // Empty string triggers retry with no input
        setTimeout(() => setErrorMessage(''), 5000);
        setGenerating(false);
        return;
      }
      
      console.log('Saving AI story to database...');
      // Step 3: Save AI's response to history via api.py
      const aiHistoryResponse = await axios.post(
        `${API_URL}/history/`,
        { entry: aiStory },
        { 
          params: { saved_game_id: game.id },
          headers: { Authorization: `Bearer ${token}` } 
        }
      );
      
      setLocalHistory(prev => [...prev, aiHistoryResponse.data]);
      
      // Refresh tokenized history and deep memory in case new chunks were created/compressed
      await fetchTokenizedHistory();
      await fetchDeepMemory();
      
    } catch (error) {
      console.error('Error during action submission:', error);
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      setErrorMessage('Failed to process action. Click the blue message to retry.');
      setFailedMessage(''); // Empty string triggers retry with no input
      setTimeout(() => setErrorMessage(''), 5000);
    } finally {
      setSubmitting(false);
      setGenerating(false);
    }
  };

  // Update placeholder text whenever actionMode changes
  useEffect(() => {
    if (actionMode === 'SPEECH') {
      setPlaceholderText('Enter what you say...');
    } else if (actionMode === 'NARRATE') {
      setPlaceholderText('Add to the story...');
    } else {
      setPlaceholderText('Enter your action...');
    }
  }, [actionMode]);

  // Calculate stats
  const totalTokenizedChunks = tokenizedHistory.length;
  const committedToDeepMemory = deepMemory?.chunks_merged || 0;

  return (
    <div className="game-screen">
      {errorMessage && (
        <div className="error-toast">
          {errorMessage}
        </div>
      )}
      <header className="game-header">
        <div className="game-title">
          {game.player_name} - {game.world_name}
        </div>
        <div className="menu-container">
          <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
            <span className="menu-icon">&#9776;</span>
          </button>
          {menuOpen && (
            <div className="menu-dropdown">
              <button className="menu-dropdown-item" onClick={() => { setMenuOpen(false); navigate('/'); }}>Main</button>
              <button className="menu-dropdown-item" onClick={() => { setMenuOpen(false); onLogout(); }}>Logout</button>
            </div>
          )}
        </div>
      </header>
      
      <main className="game-main">
        <div className="game-info-panel">
          <div className={`collapsible-section ${detailsOpen ? 'expanded' : ''}`}>
            <button 
              className="collapsible-header"
              onClick={() => setDetailsOpen(!detailsOpen)}
              aria-expanded={detailsOpen}
            >
              <span>Game Details</span>
              <span className="collapse-icon">{detailsOpen ? '▼' : '▶'}</span>
            </button>
            {detailsOpen && (
              <div className="collapsible-content">
                <div><strong>Player:</strong> {game.player_name}</div>
                <div><strong>Gender:</strong> {game.player_gender}</div>
                <div><strong>World:</strong> {game.world_name}</div>
                <div><strong>Rating:</strong> {game.rating_name}</div>
                <div><strong>History Entries:</strong> {localHistory?.length || 0}</div>
                {tokenStats && (
                  <div><strong>Active/Total Tokens:</strong> {tokenStats.active_tokens} / {tokenStats.total_tokens}</div>
                )}
              </div>
            )}
          </div>

          <div className={`collapsible-section ${tokenizedOpen ? 'expanded' : ''}`}>
            <button 
              className="collapsible-header"
              onClick={() => setTokenizedOpen(!tokenizedOpen)}
              aria-expanded={tokenizedOpen}
            >
              <span>Tokenized History</span>
              <span className="collapse-icon">{tokenizedOpen ? '\u25bc' : '\u25b6'}</span>
            </button>
            {tokenizedOpen && (
              <div className="collapsible-content">
                {localTokenized && localTokenized.length > 0 ? (
                  <div className="tokenized-list">
                    {localTokenized.map((block, idx) => (
                      <div key={block.id || idx} className="tokenized-block">
                        {editingTokenizedId === block.id ? (
                          <div className="tokenized-edit-mode">
                            <textarea
                              className="tokenized-edit-textarea"
                              value={editedTokenizedSummary}
                              onChange={(e) => setEditedTokenizedSummary(e.target.value)}
                              rows={4}
                              autoFocus
                            />
                            <div className="tokenized-edit-actions">
                              <button className="tokenized-edit-save" onClick={() => handleSaveTokenizedEdit(block.id)}>✓ Save</button>
                              <button className="tokenized-edit-cancel" onClick={handleCancelTokenizedEdit}>✕ Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <div 
                            className="tokenized-content-clickable"
                            onClick={() => handleEditTokenized(block)}
                            title="Click to edit"
                          >
                            <div className="tokenized-token-count">
                              {block.token_count || 0}/{game.tokenized_history_block_size || 230} tokens
                            </div>
                            <p className="tokenized-summary">{block.summary}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p>No tokenized history.</p>
                )}
              </div>
            )}
          </div>

          <div className={`collapsible-section ${deepMemoryOpen ? 'expanded' : ''}`}>
            <button 
              className="collapsible-header"
              onClick={() => setDeepMemoryOpen(!deepMemoryOpen)}
              aria-expanded={deepMemoryOpen}
            >
              <span>Deep Memory</span>
              <span className="collapse-icon">{deepMemoryOpen ? '\u25bc' : '\u25b6'}</span>
            </button>
            {deepMemoryOpen && (
              <div className="collapsible-content">
                {deepMemoryData ? (
                  <div className="deep-memory-container">
                    {editingDeepMemory ? (
                      <div className="tokenized-edit-mode">
                        <textarea
                          className="tokenized-edit-textarea"
                          value={editedDeepMemory}
                          onChange={(e) => setEditedDeepMemory(e.target.value)}
                          rows={6}
                          autoFocus
                        />
                        <div className="tokenized-edit-actions">
                          <button className="tokenized-edit-save" onClick={handleSaveDeepMemoryEdit}>✓ Save</button>
                          <button className="tokenized-edit-cancel" onClick={handleCancelDeepMemoryEdit}>✕ Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div 
                        className="tokenized-content-clickable"
                        onClick={handleEditDeepMemory}
                        title="Click to edit"
                      >
                        <div className="tokenized-token-count">
                          {deepMemoryData.token_count || 0} tokens | {deepMemoryData.chunks_merged || 0} chunks merged
                        </div>
                        <p className="tokenized-summary">{deepMemory}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p>No deep memory yet. Ancient events will appear here once your story is long enough.</p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="game-story-panel">
          <div className="story-header">
            <h3>Story</h3>
            <div className="mobile-toggle-buttons">
              <button className="mobile-toggle-btn" onClick={() => setMobileDetailsOpen(true)}>
                Details
              </button>
              <button className="mobile-toggle-btn" onClick={() => setMobileTokenizedOpen(true)}>
                History
              </button>
              <button className="mobile-toggle-btn" onClick={() => setMobileDeepMemoryOpen(true)}>
                Memory
              </button>
            </div>
          </div>
          <div className="story-scroll-area" ref={scrollAreaRef}>
            {localHistory && localHistory.length > 0 ? (
              <div className="story-history">
                {localHistory.map((entry, idx) => (
                  <div key={entry.id || idx} className="story-entry">
                    {editingId === entry.id ? (
                      <div className="story-edit-mode">
                        <textarea
                          className="story-edit-textarea"
                          value={editedText}
                          onChange={(e) => setEditedText(e.target.value)}
                          rows={5}
                          autoFocus
                        />
                        <div className="story-edit-actions">
                          <button className="story-edit-save" onClick={() => handleSaveEdit(entry.id)}>✓</button>
                          <button className="story-edit-cancel" onClick={handleCancelEdit}>✕</button>
                        </div>
                      </div>
                    ) : (
                      <p 
                        className="story-entry-text editable" 
                        onClick={() => handleEdit(entry)}
                        title="Click to edit"
                      >
                        {entry.entry || entry.text}
                      </p>
                    )}
                  </div>
                ))}
                {generating && (
                  <div className="story-entry generating">
                    <p className="story-entry-text"><em>AI is thinking...</em></p>
                  </div>
                )}
                {failedMessage !== null && (
                  <div className="story-entry failed" onClick={() => handleSubmit(null, failedMessage)}>
                    <p className="story-entry-text failed-text" title="Click to retry">
                      {failedMessage 
                        ? (actionMode === 'SPEECH' 
                          ? `${game.player_name} says, "${failedMessage}"` 
                          : failedMessage)
                        : '(Click to retry)'}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p>No story history yet.</p>
            )}
          </div>
          <form className="story-input-form" onSubmit={handleSubmit}>
            <div className="mode-selector">
              <button 
                type="button"
                className="mode-button"
                onClick={() => {
                  const modes = ['ACTION', 'SPEECH', 'NARRATE'];
                  const currentIndex = modes.indexOf(actionMode);
                  const nextMode = modes[(currentIndex + 1) % modes.length];
                  setActionMode(nextMode);
                  // Update placeholder text immediately
                  if (nextMode === 'SPEECH') {
                    setPlaceholderText('Enter what you say...');
                  } else if (nextMode === 'NARRATE') {
                    setPlaceholderText('Add to the story...');
                  } else {
                    setPlaceholderText('Enter your action...');
                  }
                }}
                title="Click to cycle between modes"
              >
                {actionMode === 'ACTION' && '⚔️'}
                {actionMode === 'SPEECH' && '💬'}
                {actionMode === 'NARRATE' && '📖'}
              </button>
            </div>
            <textarea
              className="story-input"
              placeholder={placeholderText}
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              disabled={submitting || generating}
              rows={2}
            />
            <button type="submit" className="story-submit" disabled={submitting || generating}>
              {submitting ? 'Saving...' : generating ? 'AI Thinking...' : '▶'}
            </button>
            <button 
              type="button" 
              className="story-undo" 
              onClick={handleUndo}
              disabled={submitting || generating || localHistory.length === 0}
              title="Undo last entry"
            >
              <span>&#x27F2;</span>
            </button>
          </form>
        </div>
      </main>

      {/* Mobile overlay panels */}
      <div className={`mobile-panel-overlay ${mobileDetailsOpen ? 'open' : ''}`} onClick={() => setMobileDetailsOpen(false)}>
        <div className={`mobile-panel ${mobileDetailsOpen ? 'open' : ''}`} onClick={(e) => e.stopPropagation()}>
          <div className="mobile-panel-header">
            <div className="mobile-panel-title">Game Details</div>
            <button className="mobile-panel-close" onClick={() => setMobileDetailsOpen(false)}>✕</button>
          </div>
          <div className="mobile-panel-content">
            <div style={{marginBottom: '8px'}}><strong>Player:</strong> {game.player_name}</div>
            <div style={{marginBottom: '8px'}}><strong>Gender:</strong> {game.player_gender}</div>
            <div style={{marginBottom: '8px'}}><strong>World:</strong> {game.world_name}</div>
            <div style={{marginBottom: '8px'}}><strong>Rating:</strong> {game.rating_name}</div>
            <div style={{marginBottom: '8px'}}><strong>History Entries:</strong> {localHistory?.length || 0}</div>
            {tokenStats && (
              <div><strong>Active/Total Tokens:</strong> {tokenStats.active_tokens} / {tokenStats.total_tokens}</div>
            )}
          </div>
        </div>
      </div>

      <div className={`mobile-panel-overlay ${mobileTokenizedOpen ? 'open' : ''}`} onClick={() => setMobileTokenizedOpen(false)}>
        <div className={`mobile-panel ${mobileTokenizedOpen ? 'open' : ''}`} onClick={(e) => e.stopPropagation()}>
          <div className="mobile-panel-header">
            <div className="mobile-panel-title">Tokenized History</div>
            <button className="mobile-panel-close" onClick={() => setMobileTokenizedOpen(false)}>✕</button>
          </div>
          <div className="mobile-panel-content">
            {localTokenized && localTokenized.length > 0 ? (
              <div className="tokenized-list">
              {localTokenized.map((block, idx) => (
                <div key={block.id || idx} className="tokenized-block">
                  {editingTokenizedId === block.id ? (
                    <div className="tokenized-edit-mode">
                      <textarea
                        className="tokenized-edit-textarea"
                        value={editedTokenizedSummary}
                        onChange={(e) => setEditedTokenizedSummary(e.target.value)}
                        rows={4}
                        autoFocus
                      />
                      <div className="tokenized-edit-actions">
                        <button className="tokenized-edit-save" onClick={() => handleSaveTokenizedEdit(block.id)}>✓ Save</button>
                        <button className="tokenized-edit-cancel" onClick={handleCancelTokenizedEdit}>✕ Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div 
                      className="tokenized-content-clickable"
                      onClick={() => handleEditTokenized(block)}
                      title="Click to edit"
                    >
                      <div className="tokenized-token-count">
                        {block.token_count || 0}/{game.tokenized_history_block_size || 230} tokens
                      </div>
                      <p className="tokenized-summary">{block.summary}</p>
                    </div>
                  )}
                </div>
                ))}
              </div>
            ) : (
              <p>No tokenized history.</p>
            )}
          </div>
        </div>
      </div>

      <div className={`mobile-panel-overlay ${mobileDeepMemoryOpen ? 'open' : ''}`} onClick={() => setMobileDeepMemoryOpen(false)}>
        <div className={`mobile-panel ${mobileDeepMemoryOpen ? 'open' : ''}`} onClick={(e) => e.stopPropagation()}>
          <div className="mobile-panel-header">
            <div className="mobile-panel-title">Deep Memory</div>
            <button className="mobile-panel-close" onClick={() => setMobileDeepMemoryOpen(false)}>✕</button>
          </div>
          <div className="mobile-panel-content">
            {deepMemoryData ? (
              <div className="deep-memory-container">
                {editingDeepMemory ? (
                  <div className="tokenized-edit-mode">
                    <textarea
                      className="tokenized-edit-textarea"
                      value={editedDeepMemory}
                      onChange={(e) => setEditedDeepMemory(e.target.value)}
                      rows={6}
                      autoFocus
                    />
                    <div className="tokenized-edit-actions">
                      <button className="tokenized-edit-save" onClick={handleSaveDeepMemoryEdit}>✓ Save</button>
                      <button className="tokenized-edit-cancel" onClick={handleCancelDeepMemoryEdit}>✕ Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div 
                    className="tokenized-content-clickable"
                    onClick={handleEditDeepMemory}
                    title="Click to edit"
                  >
                    <div className="tokenized-token-count">
                      {deepMemoryData.token_count || 0} tokens | {deepMemoryData.chunks_merged || 0} chunks merged
                    </div>
                    <p className="tokenized-summary">{deepMemory}</p>
                  </div>
                )}
              </div>
            ) : (
              <p>No deep memory yet. Ancient events will appear here once your story is long enough.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Game;
