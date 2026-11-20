from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from app.routes.deps import require_kb_key
from app.rag.sync import sync_page

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal")


class _Page(BaseModel):
    id: int | str
    title: str = ""
    type: str = "general"
    visibility: str = "general"
    content: str = ""


@router.post("/sync-page")
async def sync_one_page(page: _Page, bg: BackgroundTasks, _=Depends(require_kb_key)):
    bg.add_task(sync_page, page.model_dump())
    logger.info("KB sync triggered | page=%s title=%s", page.id, page.title)
    return {"ok": True}
