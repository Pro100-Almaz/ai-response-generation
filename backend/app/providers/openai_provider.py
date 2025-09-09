import time
import os
from typing import AsyncIterator, Dict, Any
import asyncio
from tenacity import retry, wait_exponential_jitter, stop_after_attempt, retry_if_exception_type
from pybreaker import CircuitBreaker
from openai import AsyncOpenAI
from app.core.config import settings
from app.providers.base import Provider, ChatRequest, ChatResponseChunk, ChatResponseFull

# Circuit breaker per provider
openai_breaker = CircuitBreaker(
    fail_max=settings.CB_FAIL_MAX,
    reset_timeout=settings.CB_RESET_TIMEOUT
)

def _build_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
        organization=settings.OPENAI_ORG or None,
        project=settings.OPENAI_PROJECT or None,
        timeout=settings.OPENAI_TIMEOUT_SECONDS
    )

class OpenAIProvider(Provider):

    def _to_openai_messages(self, req: ChatRequest):
        # Pass through roles/content
        return [{"role": m.role, "content": m.content} for m in req.messages]

    @retry(
        wait=wait_exponential_jitter(initial=0.5, max=6),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    @openai_breaker
    async def generate_stream(self, req: ChatRequest) -> AsyncIterator[ChatResponseChunk]:
        client = _build_client()
        created = int(time.time())
        stream = await client.chat.completions.create(
            model=req.model.replace("openai:", ""),  # accept "openai:gpt-4o-mini"
            messages=self._to_openai_messages(req),
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=True,
        )
        async for event in stream:
            # event is a ChatCompletionChunk
            choice = event.choices[0]
            delta = choice.delta.content or ""
            finish = choice.finish_reason
            yield ChatResponseChunk(
                id=event.id,
                model=event.model,
                created=created,
                delta=delta,
                finish_reason=finish,
            )
        # OpenAI client handles end of stream

    @retry(
        wait=wait_exponential_jitter(initial=0.5, max=6),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    @openai_breaker
    async def generate(self, req: ChatRequest) -> ChatResponseFull:
        client = _build_client()
        created = int(time.time())
        resp = await client.chat.completions.create(
            model=req.model.replace("openai:", ""),
            messages=self._to_openai_messages(req),
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=False,
        )
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
            "completion_tokens": getattr(resp.usage, "completion_tokens", None),
            "total_tokens": getattr(resp.usage, "total_tokens", None),
        }
        return ChatResponseFull(
            id=resp.id,
            model=resp.model,
            created=created,
            content=content,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
