from fastapi import APIRouter
from app.routes import auth, chats, users, shifts, settings, embeddings, events

router = APIRouter(prefix="/staff", tags=["staff"])
router.include_router(auth.router)
router.include_router(chats.router)
router.include_router(users.router)
router.include_router(shifts.router)
router.include_router(settings.router)
router.include_router(embeddings.router)
router.include_router(events.router)
