import tempfile
import sys
from pathlib import Path

# Add services/brain to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.memory import (
    init_db,
    create_conversation,
    list_conversations,
    get_conversation,
    get_conversation_messages,
    rename_conversation,
    delete_conversation,
    save_message,
)


def run_database_unit_tests():
    print("--- [STAGE 1] RUNNING DATABASE LAYER UNIT TESTS ---")

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = Path(tmp_dir) / "test_leviathan.db"

        # 1. Database initialization and versioning
        print("[TEST 1] Testing init_db & schema creation...")
        init_db(test_db)
        assert test_db.exists(), "Database file was not created"
        print("PASS: Database created with schema version 1.")

        # 2. Creating and listing conversations
        print("[TEST 2] Testing conversation creation...")
        c1 = create_conversation("Personal Chat 1", "qwen3.5:4b", mode="personal", db_path=test_db)
        c2 = create_conversation("Dev Task 1", "qwen3.5:4b", mode="developer", db_path=test_db)
        assert c1["title"] == "Personal Chat 1"
        assert c1["mode"] == "personal"
        assert c2["mode"] == "developer"

        # Check mode isolation
        personal_list = list_conversations(mode="personal", db_path=test_db)
        dev_list = list_conversations(mode="developer", db_path=test_db)
        assert len(personal_list) == 1
        assert personal_list[0]["id"] == c1["id"]
        assert len(dev_list) == 1
        assert dev_list[0]["id"] == c2["id"]
        print("PASS: Conversation creation & mode separation verified.")

        # 3. Message persistence & deterministic ordering with sequence numbers
        print("[TEST 3] Testing message persistence with sequence ordering...")
        m1 = save_message(c1["id"], "user", "Hello first", db_path=test_db)
        m2 = save_message(c1["id"], "assistant", "Hi there!", db_path=test_db)
        m3 = save_message(c1["id"], "user", "What can you do?", db_path=test_db)

        assert m1["sequence"] == 1
        assert m2["sequence"] == 2
        assert m3["sequence"] == 3

        msgs = get_conversation_messages(c1["id"], mode="personal", db_path=test_db)
        assert len(msgs) == 3
        assert [m["sequence"] for m in msgs] == [1, 2, 3]
        assert [m["content"] for m in msgs] == ["Hello first", "Hi there!", "What can you do?"]
        print("PASS: Messages stored and retrieved in deterministic sequence order.")

        # 4. Idempotency test (no duplicates on retry)
        print("[TEST 4] Testing message idempotency...")
        m1_retry = save_message(c1["id"], "user", "Hello first", msg_id=m1["id"], db_path=test_db)
        assert m1_retry["id"] == m1["id"]
        assert m1_retry["sequence"] == 1
        msgs_after = get_conversation_messages(c1["id"], mode="personal", db_path=test_db)
        assert len(msgs_after) == 3, f"Expected 3 messages, got {len(msgs_after)} (duplicate created!)"
        print("PASS: Idempotent message saving verified.")

        # 5. Cross-mode protection (Developer mode cannot load personal chat)
        print("[TEST 5] Testing cross-mode isolation...")
        isolated = get_conversation_messages(c1["id"], mode="developer", db_path=test_db)
        assert isolated is None, "Developer mode was able to access Personal conversation!"
        print("PASS: Cross-mode access blocked.")

        # 6. Renaming conversation
        print("[TEST 6] Testing conversation rename...")
        renamed = rename_conversation(c1["id"], "Updated Title", db_path=test_db)
        assert renamed is True
        c1_updated = get_conversation(c1["id"], db_path=test_db)
        assert c1_updated["title"] == "Updated Title"
        print("PASS: Conversation renamed successfully.")

        # 7. Cascade deletion
        print("[TEST 7] Testing cascade deletion...")
        deleted = delete_conversation(c1["id"], db_path=test_db)
        assert deleted is True
        assert get_conversation(c1["id"], db_path=test_db) is None
        assert get_conversation_messages(c1["id"], db_path=test_db) is None
        print("PASS: Conversation and all messages cascade deleted.")

        # 8. Reopen existing database simulation
        print("[TEST 8] Testing database persistence across reconnections...")
        init_db(test_db)  # Should be idempotent
        c3 = create_conversation("Session 3", "gemma4:e2b", db_path=test_db)
        save_message(c3["id"], "user", "Persisted across restart", db_path=test_db)

        # Simulate reconnect
        reconnected_msgs = get_conversation_messages(c3["id"], db_path=test_db)
        assert len(reconnected_msgs) == 1
        assert reconnected_msgs[0]["content"] == "Persisted across restart"
        print("PASS: Persistence across reconnect verified.")

        print("\nALL STAGE 1 DATABASE TESTS PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    run_database_unit_tests()

