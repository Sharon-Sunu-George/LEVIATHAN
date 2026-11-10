import sys
from pathlib import Path

# Add services/brain to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app
from core.security import get_expected_token

def run_tests():
    client = TestClient(app)
    expected_token = get_expected_token()

    print("[TEST 1] Missing token returns HTTP 401...")
    res = client.get("/health")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
    print("PASS: Missing token returned 401.")

    print("[TEST 2] Invalid token returns HTTP 401...")
    res = client.get("/health", headers={"Authorization": "Bearer invalid_fake_token_123"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
    print("PASS: Invalid token returned 401.")

    print("[TEST 3] Valid token returns HTTP 200...")
    res = client.get("/health", headers={"Authorization": f"Bearer {expected_token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "leviathan-brain"
    assert data["version"] == "0.1.0"
    print("PASS: Valid token returned 200 with expected schema.")

    print("\nALL UNIT INTEGRATION TESTS PASSED.")

if __name__ == "__main__":
    run_tests()

