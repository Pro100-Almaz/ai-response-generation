import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Header
from app.api.deps import SessionDep
from app.models import ConversationPublic, ChatHistoryPublic, ChatMessagePublic
from app.crud import (
    get_conversations,
    get_conversation,
    get_conversation_with_messages,
    delete_conversation,
    update_conversation,
    count_messages_in_conversation
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/", response_model=List[ConversationPublic])
async def list_conversations(
    session: SessionDep,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    List all conversations for the current API key.
    """
    api_key = x_api_key or "public"
    api_key_hash = str(hash(api_key))
    
    conversations = get_conversations(
        session=session,
        api_key_hash=api_key_hash,
        skip=skip,
        limit=limit
    )
    
    # Convert to public models with message count
    result = []
    for conv in conversations:
        conv_public = ConversationPublic(
            id=conv.id,
            title=conv.title,
            api_key_hash=conv.api_key_hash,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=count_messages_in_conversation(
                session=session,
                conversation_id=conv.id
            )
        )
        result.append(conv_public)
    
    return result


@router.get("/{conversation_id}", response_model=ChatHistoryPublic)
async def get_conversation_history(
    conversation_id: str,
    session: SessionDep,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Get a specific conversation with all its messages.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    
    result = get_conversation_with_messages(
        session=session,
        conversation_id=conv_uuid
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation, messages = result
    
    # Verify API key matches (optional security check)
    api_key = x_api_key or "public"
    api_key_hash = str(hash(api_key))
    if conversation.api_key_hash and conversation.api_key_hash != api_key_hash:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    # Convert to public models
    conv_public = ConversationPublic(
        id=conversation.id,
        title=conversation.title,
        api_key_hash=conversation.api_key_hash,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages)
    )
    
    messages_public = [
        ChatMessagePublic(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            model=msg.model,
            created_at=msg.created_at,
            request_id=msg.request_id,
            finish_reason=msg.finish_reason,
            prompt_tokens=msg.prompt_tokens,
            completion_tokens=msg.completion_tokens,
            total_tokens=msg.total_tokens,
            elapsed_ms=msg.elapsed_ms
        )
        for msg in messages
    ]
    
    return ChatHistoryPublic(
        conversation=conv_public,
        messages=messages_public
    )


@router.patch("/{conversation_id}")
async def update_conversation_title(
    conversation_id: str,
    title: str,
    session: SessionDep,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Update a conversation's title.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    
    # Verify conversation exists and belongs to API key
    conversation = get_conversation(session=session, conversation_id=conv_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    api_key = x_api_key or "public"
    api_key_hash = str(hash(api_key))
    if conversation.api_key_hash and conversation.api_key_hash != api_key_hash:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    updated = update_conversation(
        session=session,
        conversation_id=conv_uuid,
        title=title
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation updated successfully", "conversation_id": str(conv_uuid)}


@router.delete("/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    session: SessionDep,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Delete a conversation and all its messages.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    
    # Verify conversation exists and belongs to API key
    conversation = get_conversation(session=session, conversation_id=conv_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    api_key = x_api_key or "public"
    api_key_hash = str(hash(api_key))
    if conversation.api_key_hash and conversation.api_key_hash != api_key_hash:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    success = delete_conversation(
        session=session,
        conversation_id=conv_uuid
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted successfully"}
