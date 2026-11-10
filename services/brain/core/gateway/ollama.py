import json
from typing import AsyncIterator
import httpx
from core.gateway.base import BaseProvider, ChatRequest, StreamChunk


class OllamaProvider(BaseProvider):
    """Adapter for local Ollama instance (default: http://127.0.0.1:11434)."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        # Generous timeout for local model warm-up and CPU execution
        self.timeout = httpx.Timeout(timeout, connect=10.0, read=timeout)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}

        url = f"{self.base_url}/api/chat"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise RuntimeError(
                        f"Ollama error (HTTP {response.status_code}): {error_text.decode('utf-8', errors='replace')}"
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    done = data.get("done", False)
                    delta = data.get("message", {}).get("content", "")

                    if delta or done:
                        yield StreamChunk(delta=delta, done=done)

                    if done:
                        break
