from abc import ABC, abstractmethod
from typing import AsyncIterator, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    id: str | None = None
    created_at: int | None = None


class ChatRequest(BaseModel):
    model: str = Field(default="qwen3.5:4b", description="Model identifier to use")
    messages: list[ChatMessage]
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    conversation_id: str | None = Field(default=None, description="Optional conversation session ID")
    user_message_id: str | None = Field(default=None, description="Optional deduplication ID for user prompt")


class StreamChunk(BaseModel):
    delta: str
    done: bool = False


class BaseProvider(ABC):
    """Abstract interface for all model providers (Ollama, future cloud, etc.)."""

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """Stream response tokens as an async iterator of StreamChunks."""
        pass
