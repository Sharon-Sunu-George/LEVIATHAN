import os
import sys
from pathlib import Path
from pydantic import BaseModel


def _resolve_data_dir() -> Path:
    """Resolve a stable, persistent application data directory.
    
    In development (or when LEVI_DATA_DIR is set), uses the project's root `data/` directory.
    In standard production, uses the OS-appropriate user application data directory.
    """
    if "LEVI_DATA_DIR" in os.environ:
        p = Path(os.environ["LEVI_DATA_DIR"]).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Find project root by traversing upwards from this config file
    # config.py -> core -> brain -> services -> Levi_AI
    current = Path(__file__).resolve()
    for _ in range(5):
        current = current.parent
        if (current / "services" / "brain" / "main.py").exists():
            data_dir = current / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir

    # Fallback to user appdata
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~/.leviathan")).expanduser()
    elif sys.platform == "darwin":
        base = Path("~/Library/Application Support").expanduser()
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()

    app_data = base / "LEVIATHAN" / "data"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data



def _resolve_data_dir() -> Path:
    """Resolve a stable, persistent application data directory.
    
    In development (or when LEVI_DATA_DIR is set), uses the project's root `data/` directory.
    In standard production, uses the OS-appropriate user application data directory.
    """
    if "LEVI_DATA_DIR" in os.environ:
        p = Path(os.environ["LEVI_DATA_DIR"]).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Find project root by traversing upwards from this config file
    # config.py -> core -> brain -> services -> Levi_AI
    current = Path(__file__).resolve()
    for _ in range(5):
        current = current.parent
        if (current / "services" / "brain" / "main.py").exists():
            data_dir = current / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir

    # Fallback to user appdata
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~/.leviathan")).expanduser()
    elif sys.platform == "darwin":
        base = Path("~/Library/Application Support").expanduser()
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()

    app_data = base / "LEVIATHAN" / "data"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data


class Settings(BaseModel):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    SERVICE_NAME: str = "leviathan-brain"
    VERSION: str = "0.1.0"

    # Path where the local session token file is persisted
    TOKEN_FILE: Path = Path(__file__).resolve().parent.parent / ".session_token"

    # Resolved persistent database location
    DATA_DIR: Path = _resolve_data_dir()
    DB_PATH: Path = DATA_DIR / "leviathan.db"


    # Resolved persistent database location
    DATA_DIR: Path = _resolve_data_dir()
    DB_PATH: Path = DATA_DIR / "leviathan.db"


settings = Settings()
