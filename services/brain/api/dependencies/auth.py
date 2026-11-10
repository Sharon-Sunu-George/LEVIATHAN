from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.security import verify_session_token

bearer_scheme = HTTPBearer(auto_error=False)


def require_local_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> bool:
    """Dependency that enforces valid local Bearer token authentication."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing local authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_session_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid local authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True

