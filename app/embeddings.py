"""
Embedding pipeline — fetches KB pages, chunks them, embeds with Voyage AI,
stores vectors in the Neon chunks table.

Chunking strategy per page type:
  building  — section-split on divider lines (----), then per-room sub-split.
              Room-specific sections get room_number tagged; shared sections NULL.
              Images stripped; alt text used only to detect room scope.
  general   — paragraph-based split, no room scoping.
  department — same as general.

Access control stored per chunk (enforced at query time, not here):
  visibility=general   → tenants + admins
  visibility=staff_only/team/restricted → admins only
"""
from __future__ import annotations

import os
import re
import logging
from typing import Generator

import httpx
from bs4 import BeautifulSoup

from app import db

logger = logging.getLogger(__name__)

KB_API_BASE = os.environ.get("KB_API_BASE_URL", "").rstrip("/")
KB_API_KEY = os.environ.get("KB_API_KEY", "")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")

VOYAGE_MODEL = "voyage-3-lite"
VOYAGE_BATCH = 64        # texts per API call (safe well under 128 limit)
MAX_CHUNK_CHARS = 1200   # hard cap per chunk before embedding


# ── HTML cleaning ──────────────────────────────────────────────────────────────

def _clean_html(html: str) -> tuple[str, list[str]]:
    """
    Returns (plain_text, alt_texts).
    Block elements become newlines; <img> tags are dropped but alt collected.
    """
    soup = BeautifulSoup(html, "html.parser")

    alt_texts: list[str] = []
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt:
            alt_texts.append(alt)
        img.decompose()

    for tag in soup.find_all(["br"]):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "li"]):
        tag.insert_before("\n")
        tag.insert_after("\n")

    text = soup.get_text(separator="")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), alt_texts


# ── Room number detection ──────────────────────────────────────────────────────

_ROOM_RE = re.compile(r"\bRoom\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)

_SHARED_AREA_KEYWORDS = {
    "kitchen", "laundry", "bathroom", "shower", "hallway", "living room",
    "backyard", "balcony", "sunroom", "car park", "parking", "lobby",
    "common area", "outdoor", "garden", "rooftop",
}


def _room_from_alt(alt: str) -> str | None:
    """Extract room number from an image alt text, e.g. 'Room 3' → '3'."""
    lower = alt.lower().strip()
    if any(kw in lower for kw in _SHARED_AREA_KEYWORDS):
        return None
    m = _ROOM_RE.search(alt)
    return m.group(1) if m else None


def _dominant_room(text: str) -> str | None:
    """
    If a chunk of text mentions exactly one room number, return it.
    If it mentions multiple rooms (a list), return None — it's shared content.
    """
    rooms = set(_ROOM_RE.findall(text))
    return rooms.pop() if len(rooms) == 1 else None


# ── Splitting ──────────────────────────────────────────────────────────────────

_DIVIDER_RE = re.compile(r"-{15,}")


def _split_sections(text: str) -> list[str]:
    """Split on long horizontal divider lines used in building handbooks."""
    sections = _DIVIDER_RE.split(text)
    return [s.strip() for s in sections if s.strip()]


def _split_room_subsections(section: str) -> list[tuple[str, str | None]]:
    """
    If a section lists per-room content (Room 1\\n...\\nRoom 2\\n...) split each
    room into its own chunk. Returns [(content, room_number), ...].
    """
    # Find all "Room N" markers at the start of a line
    markers = list(re.finditer(r"(?m)^Room\s+(\d+[A-Za-z]?)\s*$", section))
    if len(markers) < 2:
        # Not a per-room breakdown — classify the whole section
        return [(section, _dominant_room(section))]

    parts: list[tuple[str, str | None]] = []
    for i, marker in enumerate(markers):
        start = marker.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(section)
        content = section[start:end].strip()
        if content:
            parts.append((content, marker.group(1)))

    # Anything before the first marker is shared preamble
    preamble = section[: markers[0].start()].strip()
    if preamble:
        parts.insert(0, (preamble, None))

    return parts


def _split_paragraphs(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long text on blank lines, respecting max_chars per chunk."""
    paras = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current)
    return chunks


# ── Page chunker ───────────────────────────────────────────────────────────────

def chunk_page(page: dict) -> list[dict]:
    """
    Chunk one KB page into embeddable dicts ready for Neon insertion.
    Each dict has the shape of the chunks table (minus id/embedding/timestamps).
    """
    html = page.get("content", "")
    page_id = str(page["id"])
    page_title = page.get("title", "")
    page_type = page.get("type", "general")
    visibility = page.get("visibility", "general")
    # property_id links building chunks to their property; NULL for general pages
    property_id: int | None = page["id"] if page_type == "building" else None

    text, alt_texts = _clean_html(html)
    if len(text) < 30:
        return []

    result: list[dict] = []
    chunk_index = 0

    if page_type == "building":
        sections = _split_sections(text)
        for section in sections:
            if len(section) < 30:
                continue
            sub_chunks = _split_room_subsections(section)
            for content, room_number in sub_chunks:
                if len(content) < 30:
                    continue
                # If a sub-chunk is still huge, split further on paragraphs
                for part in _split_paragraphs(content):
                    heading = part.split("\n")[0].strip()[:200]
                    result.append({
                        "kb_page_id": page_id,
                        "kb_page_title": page_title,
                        "kb_page_type": page_type,
                        "visibility": visibility,
                        "property_id": property_id,
                        "room_number": room_number,
                        "chunk_index": chunk_index,
                        "heading": heading,
                        "content": part[:MAX_CHUNK_CHARS],
                    })
                    chunk_index += 1
    else:
        # General / department pages — simple paragraph chunking
        for part in _split_paragraphs(text):
            heading = part.split("\n")[0].strip()[:200]
            result.append({
                "kb_page_id": page_id,
                "kb_page_title": page_title,
                "kb_page_type": page_type,
                "visibility": visibility,
                "property_id": None,
                "room_number": None,
                "chunk_index": chunk_index,
                "heading": heading,
                "content": part[:MAX_CHUNK_CHARS],
            })
            chunk_index += 1

    return result


# ── Voyage AI embeddings ───────────────────────────────────────────────────────

def _embed_batch(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Call Voyage AI and return embeddings for a batch of texts."""
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    result = vo.embed(texts, model=VOYAGE_MODEL, input_type=input_type)
    return result.embeddings


def embed_query(query: str) -> list[float]:
    """Embed a single search query (uses query input_type for better retrieval)."""
    return _embed_batch([query], input_type="query")[0]


def _batched(items: list, size: int) -> Generator:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ── Neon upsert ────────────────────────────────────────────────────────────────

def _upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Delete existing chunks for each affected page, then insert fresh ones."""
    if not chunks:
        return

    page_ids = list({c["kb_page_id"] for c in chunks})

    with db.conn() as conn:
        cur = conn.cursor()
        # Clear old chunks for these pages in one shot
        cur.execute(
            "DELETE FROM chunks WHERE kb_page_id = ANY(%s)",
            (page_ids,),
        )
        # Insert new chunks with embeddings
        for chunk, emb in zip(chunks, embeddings):
            vec = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
            cur.execute(
                """
                INSERT INTO chunks
                  (kb_page_id, kb_page_title, kb_page_type, visibility,
                   property_id, room_number, chunk_index, heading, content, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                """,
                (
                    chunk["kb_page_id"],
                    chunk["kb_page_title"],
                    chunk["kb_page_type"],
                    chunk["visibility"],
                    chunk["property_id"],
                    chunk["room_number"],
                    chunk["chunk_index"],
                    chunk["heading"],
                    chunk["content"],
                    vec,
                ),
            )
    logger.info("Upserted %d chunks for pages %s", len(chunks), page_ids)


# ── Fetch pages from KB ────────────────────────────────────────────────────────

def fetch_pages() -> list[dict]:
    """Pull all RAG-eligible pages from the KB internal API."""
    if not KB_API_BASE or not KB_API_KEY:
        raise RuntimeError("KB_API_BASE_URL and KB_API_KEY must be set")
    resp = httpx.get(
        f"{KB_API_BASE}/internal/pages",
        headers={"X-Chatbot-API-Key": KB_API_KEY},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# ── Public API ─────────────────────────────────────────────────────────────────

def sync_page(page: dict) -> int:
    """Chunk + embed + upsert a single page. Returns chunk count."""
    import time

    chunks = chunk_page(page)
    if not chunks:
        logger.info("Page %s produced no chunks (empty content)", page["id"])
        return 0

    texts = [c["content"] for c in chunks]
    embeddings: list[list[float]] = []
    for i, batch in enumerate(_batched(texts, VOYAGE_BATCH)):
        if i > 0:
            time.sleep(0.5)  # 0.5s between batches within a page
        embeddings.extend(_embed_batch(batch))

    _upsert_chunks(chunks, embeddings)
    return len(chunks)


def sync_all() -> dict:
    """Bulk ingestion — fetch all KB pages, chunk and embed everything."""
    import time

    pages = fetch_pages()
    total_chunks = 0
    skipped = 0

    for idx, page in enumerate(pages):
        try:
            n = sync_page(page)
            total_chunks += n
            if n == 0:
                skipped += 1
            else:
                # Brief pause between pages to stay under rate limits
                time.sleep(0.3)
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                logger.warning("Rate limited on page %s — waiting 20s", page["id"])
                time.sleep(20)
                try:
                    n = sync_page(page)
                    total_chunks += n
                except Exception:
                    logger.exception("Retry failed for page %s", page["id"])
                    skipped += 1
            else:
                logger.exception("Failed to sync page %s (%s)", page["id"], page.get("title"))
                skipped += 1

        if (idx + 1) % 20 == 0:
            logger.info("Progress: %d/%d pages, %d chunks so far", idx + 1, len(pages), total_chunks)

    logger.info("Bulk sync complete: %d pages, %d chunks, %d skipped",
                len(pages), total_chunks, skipped)
    return {"pages": len(pages), "chunks": total_chunks, "skipped": skipped}
