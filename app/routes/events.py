from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core import sse
from app.routes.deps import require_auth_query

router = APIRouter()


@router.get("/events")
async def events(_: dict = Depends(require_auth_query)):
    return StreamingResponse(
        sse.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
