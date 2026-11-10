from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from api.dependencies.auth import require_local_auth
from core import memory

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    model: str = Field(default="qwen3.5:4b")
    mode: Literal["personal", "developer"] = Field(default="personal")


class ConversationRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    model: str
    mode: str
    created_at: int
    updated_at: int


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sequence: int
    role: str
    content: str
    created_at: int


@router.get("", response_model=list[ConversationSummaryResponse])
def list_conversations_endpoint(
    mode: Literal["personal", "developer"] = Query(default="personal"),
    authenticated: bool = Depends(require_local_auth),
) -> list[dict]:
    """List conversations for a given mode, ordered by last updated descending."""
    return memory.list_conversations(mode=mode)


@router.post("", response_model=ConversationSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    req: ConversationCreateRequest,
    authenticated: bool = Depends(require_local_auth),
) -> dict:
    """Create a new conversation."""
    return memory.create_conversation(title=req.title, model=req.model, mode=req.mode)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def get_messages_endpoint(
    conversation_id: str,
    mode: Literal["personal", "developer"] | None = Query(default=None),
    authenticated: bool = Depends(require_local_auth),
) -> list[dict]:
    """Retrieve full chronological message history for a conversation."""
    messages = memory.get_conversation_messages(conversation_id, mode=mode)
    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or mode mismatch",
        )
    return messages


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
def rename_conversation_endpoint(
    conversation_id: str,
    req: ConversationRenameRequest,
    authenticated: bool = Depends(require_local_auth),
) -> dict:
    """Rename a conversation."""
    success = memory.rename_conversation(conversation_id, req.title)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    conv = memory.get_conversation(conversation_id)
    assert conv is not None
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_endpoint(
    conversation_id: str,
    authenticated: bool = Depends(require_local_auth),
) -> None:
    """Delete a conversation and cascade-delete its messages."""
    success = memory.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

