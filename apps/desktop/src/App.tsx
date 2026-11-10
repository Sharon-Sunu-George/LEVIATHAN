import { useState } from "react";
import { ChatContainer } from "./components/chat/ChatContainer";
import "./App.css";

export function App() {
  const [activeTab, setActiveTab] = useState<"personal" | "developer">("personal");

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand">
          <span className="brand-title">LEVIATHAN</span>
          <span className="brand-badge">Phase 0 • v0.1.0</span>
        </div>

        <nav className="mode-nav">
          <button
            type="button"
            className={`mode-tab ${activeTab === "personal" ? "active" : ""}`}
            onClick={() => setActiveTab("personal")}
          >
            Personal Assistant
          </button>
          <button
            type="button"
            className={`mode-tab ${activeTab === "developer" ? "active" : ""}`}
            onClick={() => setActiveTab("developer")}
          >
            Developer Assistant
          </button>
        </nav>
      </header>

      <main className="main-content">
        {activeTab === "personal" ? (
          <ChatContainer mode="personal" />
        ) : (
          <div style={{ padding: "2rem", color: "#94a3b8", textAlign: "center", margin: "auto 0" }}>
            <h2>Developer Assistant</h2>
            <p style={{ marginTop: "0.5rem" }}>
              OpenCode coding agent integration will be enabled in Milestone 0.5.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
