from __future__ import annotations
import os
import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from app.core import db
from app.routes.deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/embeddings")


@router.post("/sync")
async def trigger_sync(bg: BackgroundTasks, _: dict = Depends(require_admin)):
    from app.rag.sync import sync_all
    bg.add_task(sync_all)
    return {"ok": True, "message": "Bulk sync started — check Railway logs"}


@router.get("/status")
def status(_: dict = Depends(require_admin)):
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT kb_page_id) FROM chunks")
        total, pages = cur.fetchone()
        cur.execute("SELECT kb_page_type, COUNT(*) FROM chunks GROUP BY kb_page_type")
        by_type = dict(cur.fetchall())
    return {
        "chunks": total,
        "pages_indexed": pages,
        "by_type": by_type,
        "env": {
            "KB_API_BASE_URL": bool(os.environ.get("KB_API_BASE_URL")),
            "KB_API_KEY": bool(os.environ.get("KB_API_KEY")),
            "VOYAGE_API_KEY": bool(os.environ.get("VOYAGE_API_KEY")),
        },
    }
