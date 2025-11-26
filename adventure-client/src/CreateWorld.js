import React, { useState, useEffect } from "react";
import axios from "axios";
import { API_URL, AI_URL } from "./config";

function CreateWorld({ token, onBack, onWorldCreated, worldToEdit = null }) {
  const [name, setName] = useState("");
  const [preface, setPreface] = useState("");
  const [worldTokens, setWorldTokens] = useState("");
  // Lore lookup additions
  const [lookupPrompt, setLookupPrompt] = useState("");
  const [userMetaData, setUserMetaData] = useState("");
  const [lookupCommand, setLookupCommand] = useState("");
  const [loreLoading, setLoreLoading] = useState(false);
  const [loreDraft, setLoreDraft] = useState(null); // {draft_tokens, sections, sources, counts}
  const [loreError, setLoreError] = useState("");
  const [showLoreHelper, setShowLoreHelper] = useState(false); // accordion toggle
  const [errorMessage, setErrorMessage] = useState("");
  const [creating, setCreating] = useState(false);
  const [tokenCount, setTokenCount] = useState(0);
  const [maxTokens, setMaxTokens] = useState(1000);
  // maxTokens is now a prop
  const isEditMode = !!worldToEdit;

  // Populate form when editing
  useEffect(() => {
    if (worldToEdit) {
      setName(worldToEdit.name || "");
      setPreface(worldToEdit.preface || "");
      setWorldTokens(worldToEdit.world_tokens || "");
    }
  }, [worldToEdit]);

  // Fetch account level settings to determine dynamic max world tokens
  useEffect(() => {
    if (!token) return;
    axios
      .get(`${API_URL}/users/account_level/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => {
        const dynamicMax = res.data?.game_settings?.max_world_tokens;
        if (typeof dynamicMax === "number" && dynamicMax > 0) {
          setMaxTokens(dynamicMax);
        }
      })
      .catch((err) => {
        // eslint-disable-next-line
        console.warn(
          "Could not load account level settings, retaining default maxTokens. Reason:",
          err.response?.data?.detail || err.message,
        );
      });
  }, [token]);

  // Calculate token count whenever fields change (with debouncing)
  useEffect(() => {
    const combinedText = `${name} ${worldTokens}`; // do not count preface - ${preface}
    if (!combinedText.trim()) {
      setTokenCount(0);
      return;
    }

    // Debounce: wait500ms after user stops typing before counting tokens
    const timeoutId = setTimeout(async () => {
      try {
        // eslint-disable-next-line
        console.log(
          "Sending text to token counter:",
          combinedText.length,
          "characters",
        );
        const response = await axios.post(
          `${AI_URL}/count_tokens/`,
          { text: combinedText },
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );
        // eslint-disable-next-line
        console.log("Token count response:", response.data);
        setTokenCount(response.data.token_count || 0);
      } catch (err) {
        console.error("Failed to count tokens:", err);
        setErrorMessage(
          "Failed to calculate token count. AI server may be offline.",
        );
      }
    }, 500);

    // Cleanup: cancel the timeout if user types again before500ms
    return () => clearTimeout(timeoutId);
  }, [name, worldTokens, token]);

  const handleLoreLookup = async () => {
    setLoreError("");
    setLoreDraft(null);
    const prompt = lookupPrompt.trim();
    if (!prompt) {
      setLoreError("Enter a lookup prompt first.");
      return;
    }
    setLoreLoading(true);
    try {
      const response = await axios.post(
        `${AI_URL}/lore/retrieve_tokens`,
        {
          lookup_prompt: prompt,
          story_preface: preface || undefined,
          command_prompt: lookupCommand || undefined,
          meta_data: userMetaData,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setLoreDraft(response.data);
      if (!response.data?.summary?.trim()) {
        setLoreError("No lore found for that prompt. Try refining it.");
      }
    } catch (err) {
      console.error("Lore lookup failed:", err);
      setLoreError(err.response?.data?.detail || "Lore lookup failed.");
    } finally {
      setLoreLoading(false);
    }
  };

  // const handleInsertLore = () => {
  // if (!loreDraft?.draft_tokens) return;
  // // Prepend or append; choose append so user existing tokens remain primary.
  // const separator = worldTokens.trim() ? '\n\n' : '';
  // setWorldTokens(worldTokens + separator + loreDraft.draft_tokens);
  // // Clear draft after insertion to reduce repeat inserts.
  // setLoreDraft(null);
  // };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");
    setCreating(true);

    try {
      const payload = {
        name: name.trim(),
        preface: preface.trim(),
        world_tokens: worldTokens.trim(),
      };

      let response;
      if (isEditMode) {
        response = await axios.patch(
          `${API_URL}/worlds/${worldToEdit.id}`,
          payload,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );
        alert("World updated successfully!");
      } else {
        response = await axios.post(`${API_URL}/worlds/`, payload, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        alert("World created successfully!");

        // Clear form only on create
        setName("");
        setPreface("");
        setWorldTokens("");
      }

      // Call parent callback if provided
      if (onWorldCreated) {
        onWorldCreated(response.data);
      }
    } catch (err) {
      console.error(
        `Failed to ${isEditMode ? "update" : "create"} world:`,
        err,
      );
      setErrorMessage(
        err.response?.data?.detail ||
          `Failed to ${isEditMode ? "update" : "create"} world. Please try again.`,
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card modal-card-wide">
        <div className="modal-header">
          <h2>{isEditMode ? "Edit World" : "Create New World"}</h2>
          <button className="modal-close" onClick={onBack} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="modal-body">
          {errorMessage && <div className="login-error">{errorMessage}</div>}

          <div
            className={`token-counter ${tokenCount > maxTokens ? "token-counter-error" : tokenCount > maxTokens * 0.9 ? "token-counter-warning" : ""}`}
          >
            <strong>Token Count:</strong> {tokenCount} / {maxTokens}
            {tokenCount > maxTokens && (
              <span className="token-error-text"> - Exceeds limit!</span>
            )}
            {tokenCount > maxTokens * 0.9 && tokenCount <= maxTokens && (
              <span className="token-warning-text"> - Approaching limit</span>
            )}
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
              <small className="form-hint">
                Must be unique. Max64 characters.
              </small>
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
              <small className="form-hint">
                This is the entry point to the adventure.
              </small>
            </div>

            {/* Lore Lookup (Accordion) */}
            <div
              className="form-group"
              style={{
                border: "1px solid #333",
                borderRadius: "4px",
                padding: "0.5rem",
              }}
            >
              <button
                type="button"
                className="btn-secondary"
                aria-expanded={showLoreHelper}
                aria-controls="lore-helper-panel"
                onClick={() => setShowLoreHelper((v) => !v)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>
                  📚 Lore Helper{" "}
                  {lookupPrompt && `(${lookupPrompt.length} chars)`}
                </span>
                <span style={{ fontSize: "0.85rem" }}>
                  {showLoreHelper ? "▲" : "▼"}
                </span>
              </button>
              {showLoreHelper && (
                <div id="lore-helper-panel" style={{ marginTop: "0.75rem" }}>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <textarea
                      id="user-meta-data"
                      className="form-textarea"
                      style={{ width: "100%" }}
                      placeholder="Pre-sourced data, include world-tokens here for better context (optional)"
                      value={userMetaData}
                      onChange={(e) => setUserMetaData(e.target.value)}
                      rows={4}
                      disabled={creating || loreLoading}
                    />
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <input
                      id="lookup-prompt"
                      type="text"
                      className="form-input"
                      style={{ width: "30%" }}
                      placeholder="e.g. Scooby Doo, Midgar FF7 locations, Hollow Knight factions"
                      value={lookupPrompt}
                      onChange={(e) => setLookupPrompt(e.target.value)}
                      disabled={creating || loreLoading}
                    />
                    <input
                      id="lookup-command"
                      type="text"
                      className="form-input"
                      style={{ width: "70%" }}
                      placeholder="Command (e.g., 'Create a dark description of this world.')"
                      value={lookupCommand}
                      onChange={(e) => setLookupCommand(e.target.value)}
                      disabled={creating || loreLoading}
                    />
                  </div>
                  <small className="form-hint">
                    Provide franchise or thematic keywords. Generates structured
                    descriptive tokens via AI.
                  </small>
                  <div
                    style={{
                      marginTop: "0.5rem",
                      display: "flex",
                      gap: "0.5rem",
                    }}
                  >
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleLoreLookup}
                      disabled={loreLoading || !lookupPrompt.trim() || creating}
                    >
                      {loreLoading ? "Generating..." : "Generate Lore Draft"}
                    </button>
                    {/* Optional reinsertion button removed for simplified flow */}
                  </div>
                  {loreError && (
                    <div
                      className="login-error"
                      style={{ marginTop: "0.5rem" }}
                    >
                      {loreError}
                    </div>
                  )}
                  {loreDraft && !loreError && (
                    <div
                      className="preview-box"
                      style={{
                        marginTop: "0.75rem",
                        maxHeight: "220px",
                        overflowY: "auto",
                        border: "1px solid #444",
                        padding: "0.5rem",
                        width: "100%",
                      }}
                    >
                      <strong>Lore Draft Preview</strong>
                      <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                        {loreDraft.summary || "No summary."}
                      </div>
                      {loreDraft.draft_tokens && (
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            fontSize: "0.7rem",
                            marginTop: "0.5rem",
                            width: "100%",
                          }}
                        >
                          {loreDraft.draft_tokens}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              )}
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
                Keep this concise but descriptive. This context is sent to the
                AI with every request. Recommended: ~300-500 tokens.
              </small>
              {loreDraft === null && lookupPrompt.trim() && !loreLoading && (
                <small className="form-hint" style={{ color: "#888" }}>
                  Tip: Generate a lore draft above and insert it here to enrich
                  the world.
                </small>
              )}
            </div>

            <div className="form-actions">
              <button
                type="submit"
                className="btn-primary"
                disabled={
                  creating ||
                  !name.trim() ||
                  !preface.trim() ||
                  !worldTokens.trim()
                }
              >
                {creating
                  ? isEditMode
                    ? "Updating..."
                    : "Creating..."
                  : isEditMode
                    ? "Update World"
                    : "Create World"}
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
