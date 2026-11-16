from __future__ import annotations
import json
import logging
import os
import time
import httpx
from app.core import db
from app.rag.chunker import chunk_page
from app.rag import voyage

logger = logging.getLogger(__name__)


def fetch_pages() -> list[dict]:
    base = os.environ.get("KB_API_BASE_URL", "").rstrip("/")
    key = os.environ.get("KB_API_KEY", "")
    if not base or not key:
        raise RuntimeError("KB_API_BASE_URL and KB_API_KEY must be set")
    resp = httpx.get(f"{base}/internal/pages", headers={"X-Chatbot-API-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _upsert(chunks: list[dict], embeddings: list[list[float]]) -> None:
    page_ids = list({c["kb_page_id"] for c in chunks})
    with db.conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks WHERE kb_page_id = ANY(%s)", (page_ids,))
        for chunk, emb in zip(chunks, embeddings):
            vec = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
            cur.execute(
                """
                INSERT INTO chunks
                  (kb_page_id, kb_page_title, kb_page_type, visibility,
                   property_id, room_number, chunk_index, heading, content, embedding, images)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s)
                """,
                (chunk["kb_page_id"], chunk["kb_page_title"], chunk["kb_page_type"],
                 chunk["visibility"], chunk["property_id"], chunk["room_number"],
                 chunk["chunk_index"], chunk["heading"], chunk["content"], vec,
                 json.dumps(chunk.get("images", []))),
            )


def sync_page(page: dict) -> int:
    chunks = chunk_page(page)
    if not chunks:
        return 0
    texts = [c["content"] for c in chunks]
    embeddings: list[list[float]] = []
    for i, batch in enumerate(voyage.batched(texts)):
        if i > 0:
            time.sleep(0.5)
        embeddings.extend(voyage.embed_batch(batch))
    _upsert(chunks, embeddings)
    return len(chunks)


def sync_all() -> dict:
    pages = fetch_pages()
    total = 0
    skipped = 0
    for idx, page in enumerate(pages):
        try:
            n = sync_page(page)
            total += n
            if n == 0:
                skipped += 1
            else:
                time.sleep(0.3)
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                logger.warning("Rate limited on page %s — waiting 20s", page["id"])
                time.sleep(20)
                try:
                    total += sync_page(page)
                except Exception:
                    logger.exception("Retry failed for page %s", page["id"])
                    skipped += 1
            else:
                logger.exception("Failed page %s (%s)", page["id"], page.get("title"))
                skipped += 1
        if (idx + 1) % 20 == 0:
            logger.info("Progress: %d/%d pages, %d chunks", idx + 1, len(pages), total)
    logger.info("Sync complete: %d pages, %d chunks, %d skipped", len(pages), total, skipped)
    return {"pages": len(pages), "chunks": total, "skipped": skipped}
