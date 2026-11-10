import json
from typing import AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from api.dependencies.auth import require_local_auth
from core.gateway import ChatRequest, gateway
from core.persona import prepare_messages_with_persona
from core import memory

router = APIRouter(tags=["Chat"])


async def event_generator(request: ChatRequest) -> AsyncIterator[str]:
    """Formats StreamChunk items into Server-Sent Events (SSE) and persists assistant responses."""
    collected_tokens: list[str] = []
    saw_successful_done = False

    try:
        provider = gateway.get_provider_for_model(request.model)
        async for chunk in provider.stream_chat(request):
            if chunk.delta:
                collected_tokens.append(chunk.delta)

            data = json.dumps({"delta": chunk.delta, "done": chunk.done})
            yield f"data: {data}\n\n"

            if chunk.done:
                saw_successful_done = True
                break

        # Sentinel completion event
        yield "data: [DONE]\n\n"

        # Requirement: Persist assistant message ONLY after successful generation
        if saw_successful_done and request.conversation_id:
            full_assistant_reply = "".join(collected_tokens).strip()
            if full_assistant_reply:
                memory.save_message(
                    conv_id=request.conversation_id,
                    role="assistant",
                    content=full_assistant_reply,
                )

    except Exception as exc:
        error_payload = json.dumps({"error": str(exc), "done": True})
        yield f"event: error\ndata: {error_payload}\n\n"


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    authenticated: bool = Depends(require_local_auth),
) -> StreamingResponse:
    """Authenticated SSE streaming chat endpoint with LEVIATHAN system identity and persistence."""
    if not request.messages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chat request must contain at least one message",
        )

    # If conversation_id is provided, validate existence and persist the incoming user prompt
    if request.conversation_id:
        conv = memory.get_conversation(request.conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {request.conversation_id} not found",
            )

        # Requirement: Persist user message BEFORE model generation
        user_msgs = [m for m in request.messages if m.role == "user"]
        if user_msgs:
            last_user_msg = user_msgs[-1]
            memory.save_message(
                conv_id=request.conversation_id,
                role="user",
                content=last_user_msg.content,
                msg_id=request.user_message_id,
            )

    # Inject and enforce LEVIATHAN system identity exactly once at index 0
    prepared_messages = prepare_messages_with_persona(request.messages, request.model)
    enriched_request = request.model_copy(update={"messages": prepared_messages})

    return StreamingResponse(
        event_generator(enriched_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
