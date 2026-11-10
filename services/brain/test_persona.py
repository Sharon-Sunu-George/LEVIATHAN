import json
import sys
import time
import subprocess
from pathlib import Path
import httpx

# Add services/brain to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.gateway.base import ChatMessage
from core.persona import PersonaConfig, prepare_messages_with_persona, default_persona

brain_dir = Path(__file__).resolve().parent
python_exe = brain_dir / ".venv" / "Scripts" / "python.exe"
token_file = brain_dir / ".session_token"


def test_persona_unit():
    print("[TEST 1] Testing PersonaConfig defaults and prompt generation...")
    persona = PersonaConfig()
    assert persona.name == "LEVIATHAN"
    prompt = persona.get_system_prompt("qwen3.5:4b")
    assert "You are LEVIATHAN" in prompt
    assert "Never refer to yourself as Qwen, Gemma" in prompt
    assert "qwen3.5:4b" in prompt
    print("PASS: PersonaConfig correctly formats LEVIATHAN identity and model.")

    print("[TEST 2] Testing single turn system prompt injection...")
    messages = [ChatMessage(role="user", content="Hello")]
    prepared = prepare_messages_with_persona(messages, "qwen3.5:4b", persona)

    assert len(prepared) == 2, f"Expected 2 messages, got {len(prepared)}"
    assert prepared[0].role == "system"
    assert "LEVIATHAN" in prepared[0].content
    assert "qwen3.5:4b" in prepared[0].content
    assert prepared[1].role == "user"
    assert prepared[1].content == "Hello"
    print("PASS: System prompt prepended to single-turn chat.")

    print("[TEST 3] Testing multi-turn preservation without system prompt...")
    turns = [
        ChatMessage(role="user", content="Turn 1"),
        ChatMessage(role="assistant", content="Reply 1"),
        ChatMessage(role="user", content="Turn 2"),
    ]
    prepared = prepare_messages_with_persona(turns, "qwen3.5:4b", persona)
    assert len(prepared) == 4, f"Expected 4 messages, got {len(prepared)}"
    assert prepared[0].role == "system"
    assert prepared[1].content == "Turn 1"
    assert prepared[2].content == "Reply 1"
    assert prepared[3].content == "Turn 2"

    system_count = sum(1 for m in prepared if m.role == "system")
    assert system_count == 1, f"Expected exactly 1 system message, got {system_count}"
    print("PASS: Multi-turn messages preserved and exactly one system prompt present.")

    print("[TEST 4] Testing non-duplication across turns when client includes prior system prompt...")
    prior_turn = [
        ChatMessage(role="system", content="Old system prompt from previous turn"),
        ChatMessage(role="user", content="Turn 1"),
        ChatMessage(role="assistant", content="Reply 1"),
        ChatMessage(role="user", content="Turn 2"),
    ]
    prepared = prepare_messages_with_persona(prior_turn, "gemma4:e2b", persona)
    assert len(prepared) == 4, f"Expected 4 messages (1 system + 3 turns), got {len(prepared)}"
    assert prepared[0].role == "system"
    assert "gemma4:e2b" in prepared[0].content
    assert "Old system prompt" not in prepared[0].content

    system_count = sum(1 for m in prepared if m.role == "system")
    assert system_count == 1, f"Expected exactly 1 system message, got {system_count}"
    print("PASS: Existing system prompt replaced; no duplication across turns.")

    print("[TEST 5] Testing custom persona configuration...")
    custom_persona = PersonaConfig(
        name="LEVIATHAN",
        role="Expert Rust and Python Architect",
        tone="Extremely brief, terse, and code-focused",
        custom_instructions="Never use pleasantries.",
    )
    custom_prompt = custom_persona.get_system_prompt("qwen3.5:4b")
    assert "Expert Rust and Python Architect" in custom_prompt
    assert "Extremely brief" in custom_prompt
    assert "Never use pleasantries." in custom_prompt
    print("PASS: Custom persona configuration functions as expected.")

    print("\nALL PERSONA UNIT TESTS PASSED.")


def test_persona_live():
    print("\n--- RUNNING LIVE PERSONA INTEGRATION TESTS ---")
    assert token_file.exists(), "Session token missing"
    token = token_file.read_text(encoding="utf-8").strip()

    # Ensure any lingering process on 8000 is clean or start new one
    base_url = "http://127.0.0.1:8000"
    proc = None

    # Check if 8000 is already running
    is_running = False
    try:
        r = httpx.get(f"{base_url}/health", headers={"Authorization": f"Bearer {token}"}, timeout=2.0)
        if r.status_code == 200:
            is_running = True
    except Exception:
        pass

    if not is_running:
        print("Starting test FastAPI server...")
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
        time.sleep(2)

    try:
        # Test 1: Ask "What is your name?"
        print("[LIVE TEST 1] Querying: 'What is your name?'...")
        payload = {
            "model": "qwen3.5:4b",
            "messages": [{"role": "user", "content": "What is your name? Answer concisely."}],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(120.0, connect=10.0, read=120.0)

        response_tokens = []
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", f"{base_url}/chat", json=payload, headers=headers) as resp:
                assert resp.status_code == 200
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            delta = parsed.get("delta", "")
                            if delta:
                                response_tokens.append(delta)
                        except json.JSONDecodeError:
                            pass

        full_reply = "".join(response_tokens)
        print(f"Reply: {full_reply}")
        assert "LEVIATHAN" in full_reply.upper(), f"Assistant did not identify as LEVIATHAN: {full_reply}"
        print("PASS: Assistant identified as LEVIATHAN.")

        # Test 2: Ask "What model powers you?"
        print("[LIVE TEST 2] Querying: 'What model architecture powers you?'...")
        payload2 = {
            "model": "qwen3.5:4b",
            "messages": [{"role": "user", "content": "What underlying model architecture powers you? Answer concisely."}],
            "temperature": 0.0,
        }
        response_tokens2 = []
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", f"{base_url}/chat", json=payload2, headers=headers) as resp:
                assert resp.status_code == 200
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            delta = parsed.get("delta", "")
                            if delta:
                                response_tokens2.append(delta)
                        except json.JSONDecodeError:
                            pass

        full_reply2 = "".join(response_tokens2)
        print(f"Reply: {full_reply2}")
        assert "QWEN" in full_reply2.upper(), f"Assistant did not honestly identify underlying model: {full_reply2}"
        print("PASS: Assistant honestly identified underlying model.")

        print("\nALL LIVE PERSONA INTEGRATION TESTS PASSED.")

    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    test_persona_unit()
    test_persona_live()
