from __future__ import annotations
import logging
import re
from app.core import db
from app.rag.voyage import embed_query

logger = logging.getLogger(__name__)

TOP_K = 8
MIN_SCORE = 0.35


def resolve_property_id(address: str) -> int | None:
    if not address or not address.strip():
        return None
    norm = re.sub(r"\s+", " ", re.sub(r"[,.\-]", " ", address.lower().strip()))
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT property_id FROM chunks WHERE property_id IS NOT NULL AND LOWER(kb_page_title) LIKE %s LIMIT 1",
            (f"%{norm}%",),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        tokens = norm.split()
        if len(tokens) >= 2:
            cur.execute(
                "SELECT property_id FROM chunks WHERE property_id IS NOT NULL AND LOWER(kb_page_title) LIKE %s LIMIT 1",
                (f"%{' '.join(tokens[:2])}%",),
            )
            row = cur.fetchone()
            if row:
                return row[0]
    logger.warning("Could not resolve property_id for: %s", address)
    return None


def retrieve(query: str, property_address: str | None = None,
             room_number: str | None = None, admin: bool = False) -> list[dict]:
    if not query or not query.strip():
        return []
    try:
        vec = "[" + ",".join(f"{x:.8f}" for x in embed_query(query)) + "]"
    except Exception:
        logger.exception("Failed to embed query")
        return []
    if admin:
        return _search_admin(vec)
    return _search_tenant(vec, resolve_property_id(property_address or ""), room_number)


def _search_tenant(vec: str, property_id: int | None, room_number: str | None) -> list[dict]:
    with db.conn() as c:
        cur = c.cursor()
        if property_id:
            cur.execute(
                """
                SELECT content, heading, kb_page_title, kb_page_type, room_number,
                       1 - (embedding <=> %s::vector) AS similarity, images
                FROM chunks
                WHERE kb_page_type = 'building'
                  AND property_id = %s
                  AND (room_number IS NULL OR room_number = %s)
                ORDER BY similarity DESC LIMIT %s
                """,
                (vec, property_id, room_number, TOP_K),
            )
        else:
            cur.execute(
                """
                SELECT content, heading, kb_page_title, kb_page_type, room_number,
                       1 - (embedding <=> %s::vector) AS similarity, images
                FROM chunks WHERE kb_page_type = 'building' AND property_id IS NULL
                ORDER BY similarity DESC LIMIT %s
                """,
                (vec, TOP_K),
            )
        return _fmt(cur.fetchall())


def _search_admin(vec: str) -> list[dict]:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT content, heading, kb_page_title, kb_page_type, room_number, "
            "1 - (embedding <=> %s::vector) AS similarity, images FROM chunks "
            "ORDER BY similarity DESC LIMIT %s",
            (vec, TOP_K),
        )
        return _fmt(cur.fetchall())


def _fmt(rows: list) -> list[dict]:
    return [
        {"content": r[0], "heading": r[1], "kb_page_title": r[2],
         "kb_page_type": r[3], "room_number": r[4], "similarity": round(float(r[5]), 4),
         "images": r[6] or []}
        for r in rows if r[5] >= MIN_SCORE
    ]


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["### Relevant information from the Living High knowledge base:\n"]
    for i, c in enumerate(chunks, 1):
        source = c["kb_page_title"]
        if c["room_number"]:
            source += f" — Room {c['room_number']}"
        lines.append(f"[{i}] **{source}**")
        lines.append(c["content"].strip())
        lines.append("")
    lines.append("Use the above to answer the tenant's question. If the answer isn't here, say you'll check and get back to them.")
    return "\n".join(lines)
