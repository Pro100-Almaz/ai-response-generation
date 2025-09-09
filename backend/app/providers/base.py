from typing import AsyncIterator, Dict, Any, Optional, List
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    # room for future: tools, response_format, top_p, etc.

class ChatResponseChunk(BaseModel):
    id: str
    model: str
    created: int
    delta: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None  # only on final

class ChatResponseFull(BaseModel):
    id: str
    model: str
    created: int
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

class Provider:
    async def generate_stream(self, req: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        raise NotImplementedError

    async def generate(self, req: ChatRequest) -> ChatResponseFull:
        raise NotImplementedError
