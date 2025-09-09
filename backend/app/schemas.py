from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Canonical
class Message(BaseModel):
    role: str
    content: str

class MessagesRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    conversation_id: Optional[str] = None  # Optional UUID string for existing conversation

class MessagesResponse(BaseModel):
    id: str
    model: str
    created: int
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None  # UUID string of the conversation

# OpenAI compat (subset)
class OAChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False

class OAChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = None

class OAUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

class OAChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OAChoice]
    usage: Optional[OAUsage] = None
