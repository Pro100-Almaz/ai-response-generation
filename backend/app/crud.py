import uuid
from typing import Any, Optional, List
from datetime import datetime

from sqlmodel import Session, select, func

from app.models import (
    Item, ItemCreate,
    Conversation, ConversationBase, ConversationPublic,
    ChatMessage, ChatMessageBase, ChatMessagePublic
)


def create_item(*, session: Session, item_in: ItemCreate) -> Item:
    db_item = Item.model_validate(item_in)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


# Chat History CRUD Operations

def create_conversation(
    *, 
    session: Session,
    title: Optional[str] = None,
    api_key_hash: Optional[str] = None
) -> Conversation:
    """Create a new conversation"""
    db_conversation = Conversation(
        title=title,
        api_key_hash=api_key_hash,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_conversation)
    session.commit()
    session.refresh(db_conversation)
    return db_conversation


def get_conversation(
    *, 
    session: Session,
    conversation_id: uuid.UUID
) -> Optional[Conversation]:
    """Get a conversation by ID"""
    return session.get(Conversation, conversation_id)


def get_conversations(
    *,
    session: Session,
    api_key_hash: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Conversation]:
    """Get conversations, optionally filtered by API key hash"""
    query = select(Conversation)
    if api_key_hash:
        query = query.where(Conversation.api_key_hash == api_key_hash)
    query = query.order_by(Conversation.updated_at.desc())
    query = query.offset(skip).limit(limit)
    return session.exec(query).all()


def update_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    title: Optional[str] = None
) -> Optional[Conversation]:
    """Update a conversation's title and updated_at timestamp"""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        return None
    if title is not None:
        conversation.title = title
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def delete_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID
) -> bool:
    """Delete a conversation and all its messages"""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        return False
    session.delete(conversation)
    session.commit()
    return True


def create_chat_message(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model: Optional[str] = None,
    request_id: Optional[str] = None,
    finish_reason: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    elapsed_ms: Optional[int] = None
) -> ChatMessage:
    """Create a new chat message"""
    db_message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        created_at=datetime.utcnow(),
        request_id=request_id,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        elapsed_ms=elapsed_ms
    )
    session.add(db_message)
    
    # Update conversation's updated_at timestamp
    conversation = session.get(Conversation, conversation_id)
    if conversation:
        conversation.updated_at = datetime.utcnow()
        session.add(conversation)
    
    session.commit()
    session.refresh(db_message)
    return db_message


def get_chat_messages(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100
) -> List[ChatMessage]:
    """Get messages for a conversation"""
    query = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at).offset(skip).limit(limit)
    return session.exec(query).all()


def get_conversation_with_messages(
    *,
    session: Session,
    conversation_id: uuid.UUID
) -> Optional[tuple[Conversation, List[ChatMessage]]]:
    """Get a conversation with all its messages"""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        return None
    
    messages = get_chat_messages(
        session=session,
        conversation_id=conversation_id,
        limit=1000  # Get all messages
    )
    return conversation, messages


def count_messages_in_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID
) -> int:
    """Count the number of messages in a conversation"""
    query = select(func.count(ChatMessage.id)).where(
        ChatMessage.conversation_id == conversation_id
    )
    return session.exec(query).one()
