import json
import sys
import tempfile
import time
import subprocess
from pathlib import Path
import httpx

# Add services/brain to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

brain_dir = Path(__file__).resolve().parent
python_exe = brain_dir / ".venv" / "Scripts" / "python.exe"
token_file = brain_dir / ".session_token"


def run_stage2_tests():
    print("--- [STAGE 2] RUNNING CONVERSATION API & STREAMING PERSISTENCE TESTS ---")
    assert token_file.exists(), "Session token missing"
    token = token_file.read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory() as tmp_data_dir:
        # Direct the server to use our test data dir for isolated verification
        test_env = {
            **subprocess.os.environ,
            "LEVI_DATA_DIR": tmp_data_dir,
        }

        base_url = "http://127.0.0.1:8000"

        # Ensure any lingering process on 8000 is clean
        try:
            r = httpx.get(f"{base_url}/health", headers={"Authorization": f"Bearer {token}"}, timeout=1.0)
            if r.status_code == 200:
                print("Note: An existing server was on 8000, testing directly.")
        except Exception:
            pass

        proc = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ],
            cwd=str(brain_dir),
            env=test_env,
        )
        time.sleep(2)

        try:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)

            # 1. Test POST /conversations
            print("[TEST 1] Creating Personal conversation via POST /conversations...")
            res = client.post("/conversations", json={"title": "First Personal Chat", "model": "qwen3.5:4b", "mode": "personal"})
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            conv = res.json()
            conv_id = conv["id"]
            assert conv["title"] == "First Personal Chat"
            assert conv["mode"] == "personal"
            print(f"PASS: Conversation created with ID {conv_id}.")

            # 2. Test GET /conversations
            print("[TEST 2] Listing conversations via GET /conversations...")
            res_list = client.get("/conversations?mode=personal")
            assert res_list.status_code == 200
            items = res_list.json()
            assert len(items) >= 1
            assert any(item["id"] == conv_id for item in items)
            print("PASS: Conversation listed successfully.")

            # 3. Test streaming /chat with conversation_id
            print("[TEST 3] Testing SSE streaming with conversation_id persistence...")
            chat_payload = {
                "model": "qwen3.5:4b",
                "conversation_id": conv_id,
                "user_message_id": "user-msg-unique-101",
                "messages": [{"role": "user", "content": "Respond with the single word: ACKNOWLEDGED"}],
                "temperature": 0.0,
            }

            tokens = []
            timeout = httpx.Timeout(120.0, connect=10.0, read=120.0)
            with httpx.Client(timeout=timeout) as streaming_client:
                with streaming_client.stream("POST", f"{base_url}/chat", json=chat_payload, headers=headers) as resp:
                    assert resp.status_code == 200
                    for line in resp.iter_lines():
                        if line.startswith("data: "):
                            data = line[6:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(data)
                                if parsed.get("delta"):
                                    tokens.append(parsed["delta"])
                            except json.JSONDecodeError:
                                pass

            reply = "".join(tokens).strip()
            print(f"    Model reply: '{reply}'")
            assert len(reply) > 0

            # 4. Verify messages were persisted in database
            print("[TEST 4] Fetching conversation messages from GET /conversations/{id}/messages...")
            res_msgs = client.get(f"/conversations/{conv_id}/messages")
            assert res_msgs.status_code == 200
            db_msgs = res_msgs.json()
            assert len(db_msgs) == 2, f"Expected 2 messages (user + assistant), got {len(db_msgs)}"
            assert db_msgs[0]["role"] == "user"
            assert db_msgs[0]["id"] == "user-msg-unique-101"
            assert db_msgs[0]["sequence"] == 1
            assert db_msgs[1]["role"] == "assistant"
            assert db_msgs[1]["sequence"] == 2
            print("PASS: User prompt and assistant reply persisted with correct sequence numbers.")

            # 5. Test PATCH /conversations/{id} (rename)
            print("[TEST 5] Renaming conversation via PATCH /conversations/{id}...")
            res_rename = client.patch(f"/conversations/{conv_id}", json={"title": "Renamed Chat Title"})
            assert res_rename.status_code == 200
            assert res_rename.json()["title"] == "Renamed Chat Title"
            print("PASS: Conversation renamed.")

            # 6. Test DELETE /conversations/{id}
            print("[TEST 6] Deleting conversation via DELETE /conversations/{id}...")
            res_del = client.delete(f"/conversations/{conv_id}")
            assert res_del.status_code == 204
            # Verify 404 on fetch
            res_404 = client.get(f"/conversations/{conv_id}/messages")
            assert res_404.status_code == 404
            print("PASS: Conversation deleted and cascades confirmed.")

            print("\nALL STAGE 2 CONVERSATION API & STREAMING PERSISTENCE TESTS PASSED.")

        finally:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    run_stage2_tests()

