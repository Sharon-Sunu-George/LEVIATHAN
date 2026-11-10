import os
import secrets
import subprocess
import sys
from pathlib import Path
from core.config import settings

_CURRENT_SESSION_TOKEN: str | None = None


def _set_restrictive_permissions(file_path: Path) -> None:
    """Set restrictive file permissions so only the current user can read/write."""
    try:
        if sys.platform == "win32":
            # On Windows, restrict ACL using icacls: remove inheritance and grant current user full control
            username = os.environ.get("USERNAME")
            if username:
                subprocess.run(
                    [
                        "icacls",
                        str(file_path),
                        "/inheritance:r",
                        "/grant:r",
                        f"{username}:(R,W)",
                    ],
                    capture_output=True,
                    check=False,
                )
        else:
            # POSIX read/write only by owner
            file_path.chmod(0o600)
    except Exception:
        # Fallback to standard chmod if platform tooling is unavailable
        try:
            file_path.chmod(0o600)
        except OSError:
            pass


def initialize_session_token() -> str:
    """Load an existing session token or generate a new cryptographically secure token."""
    global _CURRENT_SESSION_TOKEN
    token_file = settings.TOKEN_FILE

    if token_file.exists():
        token = token_file.read_text(encoding="utf-8").strip()
        if token:
            _CURRENT_SESSION_TOKEN = token
            return _CURRENT_SESSION_TOKEN

    # Generate 256-bit cryptographically secure random token (URL-safe string)
    token = secrets.token_urlsafe(32)
    token_file.write_text(token, encoding="utf-8")
    _set_restrictive_permissions(token_file)
    _CURRENT_SESSION_TOKEN = token
    return _CURRENT_SESSION_TOKEN


def get_expected_token() -> str:
    """Return the active session token, initializing if needed."""
    global _CURRENT_SESSION_TOKEN
    if _CURRENT_SESSION_TOKEN is None:
        return initialize_session_token()
    return _CURRENT_SESSION_TOKEN


def verify_session_token(provided_token: str) -> bool:
    """Perform constant-time comparison against the active session token."""
    expected = get_expected_token()
    return secrets.compare_digest(provided_token, expected)

