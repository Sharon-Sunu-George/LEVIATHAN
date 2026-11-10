import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from core.config import settings

SCHEMA_VERSION = 1


@contextmanager
def get_db_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional SQLite connection with foreign keys and WAL enabled."""
    target_path = db_path or settings.DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 10s busy timeout for concurrent read/write safety
    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """Initialize database tables and enforce schema versioning."""
    schema_file = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    schema_sql = schema_file.read_text(encoding="utf-8")

    with get_db_connection(db_path) as conn:
        conn.executescript(schema_sql)

        # Check and record schema version
        cur = conn.execute("SELECT version FROM schema_version WHERE version = ?;", (SCHEMA_VERSION,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?);",
                (SCHEMA_VERSION, int(time.time())),
            )


def create_conversation(
    title: str,
    model: str,
    mode: str = "personal",
    conv_id: str | None = None,
    db_path: Path | None = None,
) -> dict:
    """Create a new conversation session."""
    if mode not in ("personal", "developer"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'personal' or 'developer'.")

    conversation_id = conv_id or f"conv-{uuid.uuid4().hex[:12]}"
    now = int(time.time())

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, model, mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (conversation_id, title.strip(), model, mode, now, now),
        )

    return {
        "id": conversation_id,
        "title": title.strip(),
        "model": model,
        "mode": mode,
        "created_at": now,
        "updated_at": now,
    }


def list_conversations(
    mode: str = "personal",
    db_path: Path | None = None,
) -> list[dict]:
    """List conversation summaries for a specific mode ordered by last updated."""
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, title, model, mode, created_at, updated_at
            FROM conversations
            WHERE mode = ?
            ORDER BY updated_at DESC;
            """,
            (mode,),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_conversation(
    conv_id: str,
    mode: str | None = None,
    db_path: Path | None = None,
) -> dict | None:
    """Retrieve conversation details by ID, optionally validating mode isolation."""
    query = "SELECT id, title, model, mode, created_at, updated_at FROM conversations WHERE id = ?"
    params: list[str] = [conv_id]
    if mode:
        query += " AND mode = ?"
        params.append(mode)

    with get_db_connection(db_path) as conn:
        cur = conn.execute(query, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None


def get_conversation_messages(
    conv_id: str,
    mode: str | None = None,
    db_path: Path | None = None,
) -> list[dict] | None:
    """Retrieve all messages for a conversation in deterministic sequence order.
    
    Returns None if the conversation does not exist (or does not match requested mode).
    """
    conv = get_conversation(conv_id, mode=mode, db_path=db_path)
    if conv is None:
        return None

    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, conversation_id, sequence, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY sequence ASC;
            """,
            (conv_id,),
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def rename_conversation(
    conv_id: str,
    title: str,
    mode: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Rename a conversation title and touch updated_at."""
    conv = get_conversation(conv_id, mode=mode, db_path=db_path)
    if conv is None:
        return False

    now = int(time.time())
    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?;
            """,
            (title.strip(), now, conv_id),
        )
        return cur.rowcount > 0


def delete_conversation(
    conv_id: str,
    mode: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Delete a conversation. Associated messages cascade delete automatically."""
    conv = get_conversation(conv_id, mode=mode, db_path=db_path)
    if conv is None:
        return False

    with get_db_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?;", (conv_id,))
        return cur.rowcount > 0


def save_message(
    conv_id: str,
    role: str,
    content: str,
    msg_id: str | None = None,
    created_at: int | None = None,
    db_path: Path | None = None,
) -> dict:
    """Idempotently save a message with an auto-incrementing per-conversation sequence number."""
    message_id = msg_id or f"msg-{uuid.uuid4().hex[:12]}"
    now = created_at or int(time.time())

    with get_db_connection(db_path) as conn:
        # Check idempotency: if message ID already exists, return existing row
        cur = conn.execute(
            "SELECT id, conversation_id, sequence, role, content, created_at FROM messages WHERE id = ?;",
            (message_id,),
        )
        existing = cur.fetchone()
        if existing:
            return dict(existing)

        # Calculate next per-conversation sequence number
        cur = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM messages WHERE conversation_id = ?;",
            (conv_id,),
        )
        next_seq = cur.fetchone()["next_seq"]

        conn.execute(
            """
            INSERT INTO messages (id, conversation_id, sequence, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (message_id, conv_id, next_seq, role, content, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?;",
            (now, conv_id),
        )

    return {
        "id": message_id,
        "conversation_id": conv_id,
        "sequence": next_seq,
        "role": role,
        "content": content,
        "created_at": now,
    }
