from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from api.routes.health import router as health_router
from api.routes.chat import router as chat_router
from api.routes.conversations import router as conversations_router
from core.config import settings
from core.security import initialize_session_token
from core.memory import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the local session token at startup
    initialize_session_token()
    # Initialize SQLite database schema
    init_db()
    yield


app = FastAPI(
    title="LEVIATHAN Brain",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=None,  # Disabled in production/local service to prevent unauthorized enumeration
    redoc_url=None,
)

# Register routes
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(conversations_router)

if __name__ == "__main__":
    # Bound strictly to 127.0.0.1
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
    )
