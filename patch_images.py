"""
Re-chunk all building pages and update ONLY the images column.
No Voyage API calls — reuses existing embeddings.
"""
from dotenv import load_dotenv
load_dotenv()

import json, logging, os, httpx
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

from app.core import db
from app.rag.chunker import chunk_page


def fetch_pages() -> list[dict]:
    base = os.environ.get("KB_API_BASE_URL", "").rstrip("/")
    key = os.environ.get("KB_API_KEY", "")
    resp = httpx.get(f"{base}/internal/pages", headers={"X-Chatbot-API-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def patch_images(pages: list[dict]) -> dict:
    updated = 0
    skipped = 0
    for page in pages:
        if page.get("type") != "building":
            continue
        chunks = chunk_page(page)
        if not chunks:
            continue
        page_id = str(page["id"])
        with db.conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT chunk_index FROM chunks WHERE kb_page_id = %s ORDER BY chunk_index", (page_id,))
            existing = {r[0] for r in cur.fetchall()}
            if not existing:
                skipped += 1
                continue
            for chunk in chunks:
                if chunk["chunk_index"] not in existing:
                    continue
                cur.execute(
                    "UPDATE chunks SET images = %s WHERE kb_page_id = %s AND chunk_index = %s",
                    (json.dumps(chunk.get("images", [])), page_id, chunk["chunk_index"]),
                )
                updated += 1
    return {"updated": updated, "skipped_pages": skipped}


if __name__ == "__main__":
    logger.info("Fetching pages...")
    pages = fetch_pages()
    logger.info("Patching images on %d pages...", len(pages))
    result = patch_images(pages)
    logger.info("Done: %s", result)
    print(f"\nDone: {result}")
