# LEVIATHAN

LEVIATHAN is a local-first personal AI assistant combined with an integrated AI coding agent.

## Dual Mode Vision

1. **Personal Assistant**: Natural conversations, persistent memory, internet research, computer automation, and voice interaction.
2. **Developer Assistant**: Repository understanding, code generation & editing, terminal execution, and integrated coding-agent experience.

## Technology Stack

- **Desktop Shell**: Tauri 2 (Rust) + React 19 + TypeScript + Vite
- **AI Brain Engine**: Python 3.13 + FastAPI + SQLite (standard library `sqlite3`)
- **Conversation Persistence**: Local SQLite database at `data/leviathan.db` with WAL mode & foreign key cascade
- **Configurable Persona**: Dedicated system identity module (`core/persona.py`)
- **Model Gateway**: Provider adapter pattern (`BaseProvider` -> `OllamaProvider`)
- **Coding Agent Runtime**: OpenCode (`opencode-ai` / `@opencode-ai/sdk`)
- **Local Models**: Ollama (`qwen3.5:4b`, etc.)
- **Cloud Models**: Provider-independent gateway

## Current Implementation Status

### Phase 0 Foundations:
- [x] **Milestone 0.1: Scaffolding & Brain Security**: FastAPI backend, restricted ACL session-token authentication, authenticated `/health` handshake on `127.0.0.1:8000`.
- [x] **Milestone 0.2: Model Gateway with Provider Adapter**: `BaseProvider` and `OllamaProvider` adapters, authenticated SSE streaming at `POST /chat`, local Ollama model integration.
- [x] **Milestone 0.3: Desktop Integration & Lifecycle**: Tauri 2 + React 19 interface, native Rust streaming bridge via Tauri Channels, automated child process lifecycle management for the Python Brain.
- [x] **Configurable LEVIATHAN Persona**: Separate persona module enforcing assistant identity across conversation turns without hardcoded model references.
- [x] **Milestone 0.4: SQLite Conversation Persistence**: SQLite storage in `data/leviathan.db` (zero ORMs), deterministic per-conversation sequence numbering, idempotency, pre-generation prompt persistence, authenticated `/conversations` CRUD API, native Tauri bridge commands, and React conversation history sidebar with chat switching, renaming, and deletion.
- [ ] **Milestone 0.5: OpenCode Developer Agent Integration**: Managed `opencode serve` process, workspace directory selection, tool activity streaming, and native permission controls.

## Monorepo Layout

```
Levi_AI/
├── apps/
│   └── desktop/                  # Tauri 2 + React 19 + TypeScript desktop application
│       ├── src/                  # React UI components & styles
│       │   ├── components/chat/  # Chat interface & conversation history sidebar
│       │   ├── lib/              # Tauri command invoke wrappers
│       │   └── App.tsx           # Dual-mode switcher (Personal vs Developer)
│       ├── src-tauri/            # Tauri 2 Rust application & Cargo manifests
│       │   ├── src/
│       │   │   ├── backend.rs    # Python Brain child process manager
│       │   │   ├── commands.rs   # Native Tauri commands & SSE streaming bridge
│       │   │   ├── token.rs      # Native session token resolver
│       │   │   └── lib.rs        # App initialization & graceful shutdown hook
│       │   ├── Cargo.toml        # Rust dependencies
│       │   └── Cargo.lock        # Locked Rust dependency tree
│       ├── package.json          # Pinned frontend dependencies
│       └── package-lock.json     # Locked npm dependency tree
├── services/
│   └── brain/                    # Python FastAPI AI backend
│       ├── .venv/                # Isolated virtual environment (git-ignored)
│       ├── .session_token        # Restricted local ACL session token (git-ignored)
│       ├── core/
│       │   ├── gateway/          # Model gateway with provider adapters
│       │   │   ├── base.py       # BaseProvider & standard chat models
│       │   │   ├── ollama.py     # OllamaProvider adapter
│       │   │   └── router.py     # Provider registry & model router
│       │   ├── persona.py        # Configurable LEVIATHAN system prompt & identity
│       │   ├── memory.py         # SQLite persistence repository (zero external ORMs)
│       │   ├── config.py         # Stable data directory resolution
│       │   └── security.py       # Session token generation & constant-time check
│       ├── db/
│       │   └── schema.sql        # Database schema definitions & indexing
│       ├── api/
│       │   ├── dependencies/
│       │   │   └── auth.py       # Bearer token verification
│       │   └── routes/
│       │       ├── health.py     # Authenticated /health handshake
│       │       ├── chat.py       # Authenticated SSE streaming /chat with persistence
│       │       └── conversations.py # Authenticated /conversations CRUD endpoints
│       ├── main.py               # Uvicorn entrypoint (127.0.0.1:8000)
│       ├── requirements.txt      # Pinned backend dependencies
│       ├── test_service.py       # Unit/ASGI tests
│       ├── test_gateway.py       # Gateway live streaming tests
│       ├── test_persona.py       # Persona unit & live identity tests
│       ├── test_memory.py        # SQLite persistence layer unit tests
│       ├── test_conversations_api.py # REST API & streaming persistence tests
│       └── verify_live.py        # Live HTTP network verification script
├── integrations/
│   └── opencode/                 # Reserved for OpenCode coding agent integration
├── docs/                         # Architecture & design documentation
├── scripts/                      # Developer & orchestration scripts
├── data/                         # Local database & runtime data (git-ignored)
├── .gitignore                    # Global git ignore configuration
└── README.md
```

## Prerequisites

- **Node.js**: v18+ and `npm`
- **Rust & Cargo**: Rust 1.80+ with MSVC toolchain on Windows
- **Python**: 3.11+ (Python 3.13 recommended)
- **Ollama**: Local model server running with `qwen3.5:4b` (`ollama run qwen3.5:4b`)

## Development & Verification

### 1. Setup Python Brain

```powershell
cd services/brain
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### Run Automated Test Suites:
```powershell
python test_service.py              # Health check & bearer token security
python test_gateway.py              # Model gateway SSE streaming
python test_persona.py              # System identity & multi-turn consistency
python test_memory.py               # SQLite storage layer unit tests
python test_conversations_api.py    # REST API & live chat persistence
```

### 2. Run Desktop Application (Tauri 2 + React)

```powershell
cd apps/desktop
npm install

# Run the native desktop application (automatically launches Python Brain)
npm run tauri dev
```

*The desktop application automatically manages the Python Brain child process and performs graceful termination on exit.*
