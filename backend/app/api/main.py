from fastapi import APIRouter

from app.api.routes import items, utils, messages, conversations
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(messages.router)
api_router.include_router(conversations.router)


