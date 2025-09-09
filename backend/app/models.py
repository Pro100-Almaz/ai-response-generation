import uuid
from datetime import datetime
from typing import Optional, List

from sqlmodel import Field, SQLModel, Relationship, JSON, Column
from sqlalchemy import Text


# Chat History Models

class ConversationBase(SQLModel):
    """Base model for conversations/chat sessions"""
    title: str | None = Field(default=None, max_length=255)
    api_key_hash: str | None = Field(default=None, max_length=255, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
class Conversation(ConversationBase, table=True):
    """Database model for storing conversations"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    messages: List["ChatMessage"] = Relationship(back_populates="conversation", cascade_delete=True)

class ConversationPublic(ConversationBase):
    """Public model for conversations"""
    id: uuid.UUID
    message_count: int = 0
    
class ChatMessageBase(SQLModel):
    """Base model for chat messages"""
    role: str = Field(max_length=50)  # "user", "assistant", "system"
    content: str = Field(sa_column=Column(Text))  # Using Text for unlimited length
    model: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = Field(default=None, max_length=100)
    
    # Response metadata
    finish_reason: str | None = Field(default=None, max_length=50)
    prompt_tokens: int | None = Field(default=None)
    completion_tokens: int | None = Field(default=None)
    total_tokens: int | None = Field(default=None)
    elapsed_ms: int | None = Field(default=None)

class ChatMessage(ChatMessageBase, table=True):
    """Database model for storing individual chat messages"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversation.id")
    conversation: Conversation = Relationship(back_populates="messages")
    
class ChatMessagePublic(ChatMessageBase):
    """Public model for chat messages"""
    id: uuid.UUID
    conversation_id: uuid.UUID

class ChatHistoryPublic(SQLModel):
    """Response model for chat history with messages"""
    conversation: ConversationPublic
    messages: List[ChatMessagePublic]

# Item Models (existing)

class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str
