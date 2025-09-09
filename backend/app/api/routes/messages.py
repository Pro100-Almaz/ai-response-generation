import json
import time
import uuid
import asyncio
from typing import AsyncIterator, Dict, Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlmodel import Session
import structlog
from app.schemas import (
    MessagesRequest, MessagesResponse,
    OAChatCompletionRequest, OAChatCompletionResponse, OAChoice, OAUsage, Message
)
from app.services.router import resolve_provider
from app.providers.base import ChatRequest, ChatMessage
from app.utils.rate_limit import get_limiter
from app.utils.idempotency import get_cached_response, set_cached_response
from app.utils.usage_callback import send_usage
from app.core.config import settings
from app.api.deps import SessionDep
from app.core.db import engine
from app.crud import (
    create_conversation, 
    get_conversation,
    create_chat_message,
    update_conversation
)

router = APIRouter(prefix="/messages", tags=["messages"])
logger = structlog.get_logger()

def _sse_format(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

async def _stream_with_timeout(generator: AsyncIterator[str], timeout_seconds: int = 300) -> AsyncIterator[str]:
    """Wrapper to add timeout to streaming generators"""
    try:
        async with asyncio.timeout(timeout_seconds):
            async for chunk in generator:
                yield chunk
    except asyncio.TimeoutError:
        logger.error("Streaming timeout exceeded", timeout_seconds=timeout_seconds)
        yield _sse_format({"error": "Stream timeout exceeded"})
        yield "data: [DONE]\n\n"

async def _canonical_handler(payload: MessagesRequest, api_key: str, idem_key: str | None, request_id: str, session: Optional[Session] = None):
    # Rate limit per API key
    limiter = get_limiter(api_key)
    async with limiter:
        # Idempotency only for non-streamed requests
        if idem_key and not payload.stream:
            cached = await get_cached_response(idem_key)
            if cached:
                return JSONResponse(content=cached)

        provider, normalized = resolve_provider(payload.model)
        req = ChatRequest(
            model=normalized,
            messages=[ChatMessage(**m.model_dump()) for m in payload.messages],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            stream=payload.stream,
        )
        
        # Handle conversation persistence if session is provided
        conversation = None
        conversation_id: Optional[uuid.UUID] = None
        if session:
            api_key_hash = str(hash(api_key))
            
            # Get or create conversation
            if payload.conversation_id:
                try:
                    conv_uuid = uuid.UUID(payload.conversation_id)
                    conversation = get_conversation(session=session, conversation_id=conv_uuid)
                except (ValueError, TypeError):
                    pass  # Invalid UUID, create new conversation
            
            if not conversation:
                # Create new conversation with first message as title
                title = None
                if payload.messages:
                    # Use first user message as title (truncated)
                    for msg in payload.messages:
                        if msg.role == "user":
                            title = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            break
                conversation = create_conversation(
                    session=session,
                    title=title,
                    api_key_hash=api_key_hash
                )
            # Capture the ID and avoid holding onto an ORM instance beyond the request lifecycle
            if conversation:
                conversation_id = conversation.id
            
            # Save all incoming messages to database
            if conversation_id:
                for msg in payload.messages:
                    create_chat_message(
                        session=session,
                        conversation_id=conversation_id,
                        role=msg.role,
                        content=msg.content,
                        model=normalized,
                        request_id=request_id
                    )

        if payload.stream:
            async def event_gen() -> AsyncIterator[str]:
                tokens = 0
                start = time.time()
                last_chunk = None
                full_content = ""
                try:
                    async for chunk in provider.generate_stream(req):
                        if chunk.delta:
                            tokens += 1
                            full_content += chunk.delta
                        last_chunk = chunk
                        response_data = {
                            "id": chunk.id,
                            "model": chunk.model,
                            "created": chunk.created,
                            "delta": chunk.delta,
                            "finish_reason": chunk.finish_reason,
                        }
                        # Add conversation_id to first chunk if we have one
                        if conversation_id and tokens == 1:
                            response_data["conversation_id"] = str(conversation_id)
                        yield _sse_format(response_data)
                    
                    # final sentinel
                    yield "data: [DONE]\n\n"
                    
                except Exception as e:
                    logger.error("Error during streaming", error=str(e), request_id=request_id)
                    # Send error event and close stream properly
                    error_data = {
                        "error": "Streaming error occurred",
                        "message": str(e)
                    }
                    yield _sse_format(error_data)
                    yield "data: [DONE]\n\n"
                finally:
                    # Save assistant response to database after streaming completes (in background)
                    if conversation_id and full_content:
                        try:
                            elapsed_ms = int((time.time() - start) * 1000)
                            # Use a fresh session since the request-scoped session may be closed by now
                            with Session(engine) as bg_session:
                                create_chat_message(
                                    session=bg_session,
                                    conversation_id=conversation_id,
                                    role="assistant",
                                    content=full_content,
                                    model=last_chunk.model if last_chunk else normalized,
                                    request_id=request_id,
                                    finish_reason=last_chunk.finish_reason if last_chunk else None,
                                    elapsed_ms=elapsed_ms
                                )
                        except Exception as e:
                            logger.error("Error saving message to database", error=str(e), request_id=request_id)
                    
                    # async usage callback
                    try:
                        usage_payload = {
                            "request_id": request_id,
                            "api_key_hash": hash(api_key),
                            "model": req.model,
                            "stream": True,
                            "tokens_count_approx": tokens,
                            "elapsed_ms": int((time.time() - start) * 1000),
                        }
                        await send_usage(usage_payload)
                    except Exception as e:
                        logger.error("Error sending usage callback", error=str(e), request_id=request_id)

            return StreamingResponse(
                _stream_with_timeout(event_gen()), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )

        # Non-stream path
        start = time.time()
        res = await provider.generate(req)
        
        # Save assistant response to database if session is provided
        if session and conversation:
            elapsed_ms = int((time.time() - start) * 1000)
            create_chat_message(
                session=session,
                conversation_id=conversation.id,
                role="assistant",
                content=res.content,
                model=res.model,
                request_id=request_id,
                finish_reason=res.finish_reason,
                prompt_tokens=res.usage.get("prompt_tokens") if res.usage else None,
                completion_tokens=res.usage.get("completion_tokens") if res.usage else None,
                total_tokens=res.usage.get("total_tokens") if res.usage else None,
                elapsed_ms=elapsed_ms
            )
        
        body = MessagesResponse(
            id=res.id,
            model=res.model,
            created=res.created,
            content=res.content,
            finish_reason=res.finish_reason,
            usage=res.usage,
        ).model_dump()
        
        # Add conversation_id to response if we have one
        if conversation_id:
            body["conversation_id"] = str(conversation_id)
        
        # cache if idempotency enabled
        if idem_key:
            await set_cached_response(idem_key, body)
        # fire and forget usage callback
        await send_usage({
            "request_id": request_id,
            "api_key_hash": hash(api_key),
            "model": req.model,
            "stream": False,
            "usage": res.usage,
            "elapsed_ms": int((time.time() - start) * 1000),
        })
        return JSONResponse(content=body)

@router.post("/")
async def create_message(
    payload: MessagesRequest,
    request: Request,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    request_id = request.state.request_id
    api_key = x_api_key or "public"
    return await _canonical_handler(payload, api_key, idempotency_key, request_id, session)

# OpenAI-compatible shim (subset)
@router.post("/chat/completions")
async def chat_completions(
    payload: OAChatCompletionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    request_id = request.state.request_id
    # Make API key optional - use a default if not provided
    api_key = x_api_key or "public"

    # just map to canonical and then re-wrap response to OpenAI format
    canon = MessagesRequest(
        model=payload.model if payload.model.startswith("openai:") else f"openai:{payload.model}",
        messages=[Message(**m.model_dump()) for m in payload.messages],
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        stream=payload.stream,
    )

    if canon.stream:
        # stream out OpenAI-style chunks
        limiter = get_limiter(api_key)
        async with limiter:
            provider, _ = resolve_provider(canon.model)
            req = ChatRequest(
                model=canon.model,
                messages=[ChatMessage(**m.model_dump()) for m in canon.messages],
                temperature=canon.temperature,
                max_tokens=canon.max_tokens,
                stream=True,
            )
            async def sse_gen():
                tokens = 0
                try:
                    async for chunk in provider.generate_stream(req):
                        if chunk.delta:
                            tokens += 1
                        data = {
                            "id": chunk.id,
                            "object": "chat.completion.chunk",
                            "created": chunk.created,
                            "model": chunk.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk.delta},
                                "finish_reason": chunk.finish_reason
                            }]
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error("Error during OpenAI streaming", error=str(e), request_id=request_id)
                    # Send error event and close stream properly
                    error_data = {
                        "error": {
                            "message": f"Streaming error: {str(e)}",
                            "type": "streaming_error"
                        }
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                finally:
                    # async usage callback
                    try:
                        await send_usage({
                            "request_id": request_id,
                            "api_key_hash": hash(api_key),
                            "model": req.model,
                            "stream": True,
                            "tokens_count_approx": tokens,
                        })
                    except Exception as e:
                        logger.error("Error sending usage callback", error=str(e), request_id=request_id)
            return StreamingResponse(
                _stream_with_timeout(sse_gen()), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )

    # non-stream path via canonical (without DB persistence for OpenAI compat endpoint)
    resp = await _canonical_handler(canon, api_key, idempotency_key, request_id, session=None)
    # resp is JSONResponse already
    payload_json = json.loads(resp.body.decode("utf-8"))
    oa = OAChatCompletionResponse(
        id=payload_json["id"],
        created=payload_json["created"],
        model=payload_json["model"],
        choices=[OAChoice(
            index=0,
            message=Message(role="assistant", content=payload_json["content"]),
            finish_reason=payload_json.get("finish_reason"),
        )],
        usage=OAUsage(**(payload_json.get("usage") or {}))
    )
    return JSONResponse(content=oa.model_dump())
