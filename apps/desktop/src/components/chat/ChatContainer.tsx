import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ChatMessage,
  HealthStatus,
  ConversationSummary,
  checkBrainHealth,
  streamChatMessage,
  cancelChatMessage,
  listConversations,
  createConversation,
  getConversationMessages,
  renameConversation,
  deleteConversation,
} from "../../lib/chatApi";

const AVAILABLE_MODELS = [
  { id: "qwen3.5:4b", name: "Qwen 3.5 (4B) • Local" },
  { id: "gemma4:e2b", name: "Gemma 4 (e2b) • Local" },
];

interface ChatContainerProps {
  mode?: "personal" | "developer";
}

export function ChatContainer({ mode = "personal" }: ChatContainerProps) {
  // Conversation state
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Inline rename state
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitleInput, setEditTitleInput] = useState("");

  // Deletion confirm state
  const [deletingConvId, setDeletingConvId] = useState<string | null>(null);

  // Chat message state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("qwen3.5:4b");
  const [isStreaming, setIsStreaming] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(true);

  const activeRequestIdRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const renameInputRef = useRef<HTMLInputElement | null>(null);

  // Health check on mount and interval
  useEffect(() => {
    let mounted = true;

    async function checkStatus() {
      setIsCheckingHealth(true);
      try {
        const res = await checkBrainHealth();
        if (mounted) setHealth(res);
      } catch (err) {
        if (mounted) {
          setHealth({
            healthy: false,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      } finally {
        if (mounted) setIsCheckingHealth(false);
      }
    }

    checkStatus();
    const timer = setInterval(checkStatus, 10000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  // Fetch conversations for the current mode
  const fetchConversationsList = useCallback(async () => {
    try {
      setLoadingConversations(true);
      const list = await listConversations(mode);
      setConversations(list);
      return list;
    } catch (err) {
      console.error("Failed to load conversations:", err);
      return [];
    } finally {
      setLoadingConversations(false);
    }
  }, [mode]);

  // Initial conversation load
  useEffect(() => {
    fetchConversationsList().then((list) => {
      // If we don't have an active conversation, auto-select the latest if available
      if (list && list.length > 0 && !activeConversationId) {
        selectConversation(list[0].id);
      }
    });
  }, [fetchConversationsList]);

  // Select and load messages for a conversation
  const selectConversation = async (convId: string) => {
    if (isStreaming) return;
    setActiveConversationId(convId);
    setLoadingMessages(true);
    try {
      const dbMsgs = await getConversationMessages(convId, mode);
      const chatMsgs: ChatMessage[] = dbMsgs.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant" | "system",
        content: m.content,
        timestamp: m.created_at * 1000,
        sequence: m.sequence,
      }));
      setMessages(chatMsgs);
    } catch (err) {
      console.error("Failed to load messages for conversation:", err);
    } finally {
      setLoadingMessages(false);
    }
  };

  // Create fresh new chat (local unpersisted until first message)
  const handleNewChat = () => {
    if (isStreaming) return;
    setActiveConversationId(null);
    setMessages([]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  // Auto-scroll on new messages or streaming tokens
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Focus rename input when editing starts
  useEffect(() => {
    if (editingConvId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [editingConvId]);

  // Dynamic textarea height
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140
      )}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    let targetConvId = activeConversationId;

    // If starting a fresh chat, persist a new conversation container first
    if (!targetConvId) {
      try {
        const titleSnippet =
          text.length > 32 ? text.slice(0, 32).trim() + "..." : text;
        const newConv = await createConversation(
          titleSnippet,
          selectedModel,
          mode
        );
        targetConvId = newConv.id;
        setActiveConversationId(newConv.id);
        setConversations((prev) => [newConv, ...prev]);
      } catch (err) {
        console.error("Failed to auto-create conversation:", err);
        return;
      }
    }

    const userMessageId = `user-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    const userMessage: ChatMessage = {
      id: userMessageId,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };

    const assistantPlaceholderId = `assistant-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    const assistantMessage: ChatMessage = {
      id: assistantPlaceholderId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages([...updatedMessages, assistantMessage]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    activeRequestIdRef.current = requestId;
    setIsStreaming(true);

    const apiMessages = updatedMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      await streamChatMessage(
        selectedModel,
        apiMessages,
        requestId,
        (chunk) => {
          if (chunk.error) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholderId
                  ? {
                      ...m,
                      content:
                        m.content +
                        (m.content ? "\n\n" : "") +
                        `⚠️ [Error: ${chunk.error}]`,
                    }
                  : m
              )
            );
          } else if (chunk.delta) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantPlaceholderId
                  ? { ...m, content: m.content + chunk.delta }
                  : m
              )
            );
          }

          if (chunk.done) {
            setIsStreaming(false);
            activeRequestIdRef.current = null;
            // Refresh conversation list to update timestamp ordering
            fetchConversationsList();
          }
        },
        targetConvId,
        userMessageId
      );
    } catch (err) {
      const errText = err instanceof Error ? err.message : String(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantPlaceholderId
            ? {
                ...m,
                content:
                  m.content +
                  (m.content ? "\n\n" : "") +
                  `⚠️ [Request failed: ${errText}]`,
              }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      activeRequestIdRef.current = null;
    }
  };

  const handleStop = async () => {
    if (activeRequestIdRef.current) {
      await cancelChatMessage(activeRequestIdRef.current);
      activeRequestIdRef.current = null;
      setIsStreaming(false);
    }
  };

  // Start renaming a conversation
  const startRename = (conv: ConversationSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setEditTitleInput(conv.title);
  };

  // Save renamed conversation
  const saveRename = async (convId: string) => {
    const trimmed = editTitleInput.trim();
    if (trimmed) {
      try {
        const updated = await renameConversation(convId, trimmed);
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? updated : c))
        );
      } catch (err) {
        console.error("Failed to rename conversation:", err);
      }
    }
    setEditingConvId(null);
  };

  // Confirm and execute conversation deletion
  const handleDelete = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        setActiveConversationId(null);
        setMessages([]);
      }
      setDeletingConvId(null);
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  return (
    <div className="chat-layout-wrapper">
      {/* Left Sidebar: Conversation History */}
      <aside className="chat-sidebar">
        <div className="sidebar-header">
          <button
            type="button"
            className="new-chat-button"
            onClick={handleNewChat}
            disabled={isStreaming}
          >
            <span className="plus-icon">+</span>
            <span>New Chat</span>
          </button>
        </div>

        <div className="conversations-list">
          {loadingConversations ? (
            <div className="sidebar-loading">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="sidebar-empty">No conversations yet</div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isEditing = conv.id === editingConvId;
              const isConfirmingDelete = conv.id === deletingConvId;

              return (
                <div
                  key={conv.id}
                  className={`conversation-item ${isActive ? "active" : ""}`}
                  onClick={() => selectConversation(conv.id)}
                >
                  <span className="conv-icon">💬</span>

                  <div className="conv-title-wrapper">
                    {isEditing ? (
                      <input
                        ref={renameInputRef}
                        type="text"
                        className="rename-input"
                        value={editTitleInput}
                        onChange={(e) => setEditTitleInput(e.target.value)}
                        onBlur={() => saveRename(conv.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveRename(conv.id);
                          if (e.key === "Escape") setEditingConvId(null);
                        }}
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="conv-title" title={conv.title}>
                        {conv.title}
                      </span>
                    )}
                  </div>

                  <div className="conv-actions" onClick={(e) => e.stopPropagation()}>
                    {isConfirmingDelete ? (
                      <div className="delete-confirm-box">
                        <button
                          type="button"
                          className="confirm-del-btn"
                          title="Confirm Delete"
                          onClick={(e) => handleDelete(conv.id, e)}
                        >
                          ✓
                        </button>
                        <button
                          type="button"
                          className="cancel-del-btn"
                          title="Cancel"
                          onClick={() => setDeletingConvId(null)}
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="icon-action-btn"
                          title="Rename"
                          disabled={isStreaming}
                          onClick={(e) => startRename(conv, e)}
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className="icon-action-btn delete-btn"
                          title="Delete"
                          disabled={isStreaming}
                          onClick={() => setDeletingConvId(conv.id)}
                        >
                          🗑
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* Main Chat Panel */}
      <div className="chat-container">
        {/* Top Bar with Model Selector and Backend Status */}
        <div className="chat-topbar">
          <div className="model-selector-group">
            <label htmlFor="model-select" className="model-label">
              Model:
            </label>
            <select
              id="model-select"
              className="model-select"
              value={selectedModel}
              disabled={isStreaming}
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          <div className="health-badge-group">
            <span
              className={`health-dot ${
                isCheckingHealth
                  ? "checking"
                  : health?.healthy
                  ? "online"
                  : "offline"
              }`}
            />
            <span className="health-text">
              {isCheckingHealth
                ? "Connecting..."
                : health?.healthy
                ? "Brain Online (127.0.0.1:8000)"
                : "Brain Disconnected"}
            </span>
            {!health?.healthy && !isCheckingHealth && (
              <button
                type="button"
                className="retry-btn"
                onClick={() => checkBrainHealth().then(setHealth)}
              >
                Retry
              </button>
            )}
          </div>
        </div>

        {/* Disconnected Warning Banner if Backend is down */}
        {!isCheckingHealth && health && !health.healthy && (
          <div className="disconnected-banner">
            ⚠️ Python Brain is not responding on <code>127.0.0.1:8000</code>.
            {health.error ? ` Details: ${health.error}` : ""}
          </div>
        )}

        {/* Messages Scroll Area */}
        <div className="messages-area">
          {loadingMessages ? (
            <div className="messages-loading">Loading conversation history...</div>
          ) : messages.length === 0 ? (
            <div className="empty-chat-state">
              <div className="empty-icon">🪐</div>
              <h2 className="empty-title">Welcome to LEVIATHAN</h2>
              <p className="empty-desc">
                Your local-first AI assistant is ready. Pick a model and start a
                conversation.
              </p>
              <div className="prompt-suggestions">
                <button
                  type="button"
                  className="suggestion-pill"
                  onClick={() => {
                    setInput("Hello LEVIATHAN! Who are you?");
                    textareaRef.current?.focus();
                  }}
                >
                  "Hello LEVIATHAN! Who are you?"
                </button>
                <button
                  type="button"
                  className="suggestion-pill"
                  onClick={() => {
                    setInput("What are your current core capabilities?");
                    textareaRef.current?.focus();
                  }}
                >
                  "What are your current core capabilities?"
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`message-bubble-row ${
                  msg.role === "user" ? "user-row" : "assistant-row"
                }`}
              >
                <div className="avatar-icon">
                  {msg.role === "user" ? "👤" : "⚡"}
                </div>
                <div
                  className={`message-bubble ${
                    msg.role === "user" ? "user-bubble" : "assistant-bubble"
                  }`}
                >
                  <div className="message-content">
                    {msg.content ? (
                      msg.content
                    ) : isStreaming && msg.role === "assistant" ? (
                      <span className="streaming-cursor">Thinking...</span>
                    ) : (
                      ""
                    )}
                    {isStreaming &&
                      msg.role === "assistant" &&
                      msg.content && (
                        <span className="typing-caret" />
                      )}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Sticky Input Area */}
        <div className="input-bar-container">
          <div className="input-box-wrapper">
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder={
                health?.healthy
                  ? "Type a message... (Enter to send, Shift+Enter for newline)"
                  : "Waiting for Brain backend to connect..."
              }
              value={input}
              disabled={!health?.healthy || isStreaming}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
            />

            <div className="input-action-buttons">
              {isStreaming ? (
                <button
                  type="button"
                  className="stop-button"
                  onClick={handleStop}
                  title="Stop Generation"
                >
                  <span className="stop-square" />
                  Stop
                </button>
              ) : (
                <button
                  type="button"
                  className="send-button"
                  onClick={handleSend}
                  disabled={!input.trim() || !health?.healthy}
                  title="Send Message"
                >
                  Send ➔
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
