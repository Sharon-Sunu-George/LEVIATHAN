import json
import sys
import time
import subprocess
from pathlib import Path
import httpx

brain_dir = Path(__file__).resolve().parent
python_exe = brain_dir / ".venv" / "Scripts" / "python.exe"
token_file = brain_dir / ".session_token"


def run_tests():
    print("[1] Verifying session token...")
    assert token_file.exists(), "Session token does not exist. Run main.py or verify_live.py first."
    token = token_file.read_text(encoding="utf-8").strip()

    print("[2] Starting live FastAPI server on 127.0.0.1:8000...")
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
    )

    try:
        time.sleep(2)
        base_url = "http://127.0.0.1:8000"

        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            # 1. Test POST /chat without auth -> 401
            print("[3] Testing POST /chat without token...")
            payload = {
                "model": "qwen3.5:4b",
                "messages": [{"role": "user", "content": "hello"}],
            }
            res_unauth = client.post("/chat", json=payload)
            print(f"    Status: {res_unauth.status_code} (Expected 401)")
            assert res_unauth.status_code == 401

            # 2. Test POST /chat with empty messages -> 422
            print("[4] Testing POST /chat with empty messages...")
            res_empty = client.post(
                "/chat",
                json={"model": "qwen3.5:4b", "messages": []},
                headers={"Authorization": f"Bearer {token}"},
            )
            print(f"    Status: {res_empty.status_code} (Expected 422)")
            assert res_empty.status_code == 422

        # 3. Test live SSE streaming with valid token
        print("[5] Testing live SSE streaming with local Ollama (qwen3.5:4b)...")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        chat_payload = {
            "model": "qwen3.5:4b",
            "messages": [
                {"role": "user", "content": "Respond with exactly the single word: LEVIATHAN"}
            ],
            "temperature": 0.0,
        }

        tokens_received = []
        saw_done = False

        # Set 120s timeout for stream read to accommodate local model inference
        timeout = httpx.Timeout(120.0, connect=10.0, read=120.0)
        with httpx.Client(timeout=timeout) as streaming_client:
            with streaming_client.stream(
                "POST",
                f"{base_url}/chat",
                json=chat_payload,
                headers=headers,
            ) as response:
                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                assert "text/event-stream" in response.headers.get("content-type", "")

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        raw_data = line[len("data: ") :]
                        if raw_data == "[DONE]":
                            saw_done = True
                            break
                        try:
                            parsed = json.loads(raw_data)
                            delta = parsed.get("delta", "")
                            if delta:
                                tokens_received.append(delta)
                            if parsed.get("done", False):
                                saw_done = True
                        except json.JSONDecodeError:
                            pass

        full_reply = "".join(tokens_received).strip()
        print(f"    Stream received tokens: {tokens_received}")
        print(f"    Full reconstructed reply: '{full_reply}'")
        print(f"    Stream completed with [DONE]: {saw_done}")

        assert len(tokens_received) > 0, "No tokens received from model stream"
        assert saw_done, "Did not receive completion signal"

        print("\nGATEWAY & SSE STREAMING TESTS: ALL PASSED.")

    finally:
        print("[6] Terminating test server...")
        proc.terminate()
        proc.wait(timeout=5)
        print("    Server terminated cleanly.")


if __name__ == "__main__":
    run_tests()
