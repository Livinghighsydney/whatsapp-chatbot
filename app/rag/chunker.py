from __future__ import annotations
import re
from app.rag.html import clean, dominant_room, extract_heading_images

MAX_CHARS = 1200
_DIVIDER_RE = re.compile(r"-{15,}")


def _split_sections(text: str) -> list[str]:
    return [s.strip() for s in _DIVIDER_RE.split(text) if s.strip()]


def _split_room_subsections(section: str) -> list[tuple[str, str | None]]:
    markers = list(re.finditer(r"(?m)^Room\s+(\d+[A-Za-z]?)\s*$", section))
    if len(markers) < 2:
        return [(section, dominant_room(section))]
    parts: list[tuple[str, str | None]] = []
    for i, marker in enumerate(markers):
        start = marker.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(section)
        content = section[start:end].strip()
        if content:
            parts.append((content, marker.group(1)))
    preamble = section[: markers[0].start()].strip()
    if preamble:
        parts.insert(0, (preamble, None))
    return parts


def _split_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > MAX_CHARS:
            chunks.append(current)
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current)
    return chunks


def _split_html_sections(html: str) -> list[str]:
    """Split raw HTML on divider lines so we can extract images per section."""
    return [s.strip() for s in _DIVIDER_RE.split(html) if s.strip()]


def chunk_page(page: dict) -> list[dict]:
    html = page.get("content", "")
    text, _ = clean(html)
    if len(text) < 30:
        return []

    page_id = str(page["id"])
    page_type = page.get("type", "general")
    property_id: int | None = page["id"] if page_type == "building" else None
    base = {
        "kb_page_id": page_id,
        "kb_page_title": page.get("title", ""),
        "kb_page_type": page_type,
        "visibility": page.get("visibility", "general"),
        "property_id": property_id,
    }

    result: list[dict] = []
    idx = 0

    if page_type == "building":
        html_sections = _split_html_sections(html)
        text_sections = _split_sections(text)
        for i, section in enumerate(text_sections):
            if len(section) < 30:
                continue
            # Extract heading+image pairs from the matching HTML section
            section_images = extract_heading_images(html_sections[i]) if i < len(html_sections) else []
            first_chunk_in_section = True
            for content, room_number in _split_room_subsections(section):
                if len(content) < 30:
                    continue
                for part in _split_paragraphs(content):
                    # Images go onto the first chunk of this section only
                    images = section_images if first_chunk_in_section else []
                    result.append({**base, "room_number": room_number,
                                   "chunk_index": idx, "heading": part.split("\n")[0].strip()[:200],
                                   "content": part[:MAX_CHARS], "images": images})
                    idx += 1
                    first_chunk_in_section = False
    else:
        for part in _split_paragraphs(text):
            result.append({**base, "room_number": None,
                           "chunk_index": idx, "heading": part.split("\n")[0].strip()[:200],
                           "content": part[:MAX_CHARS], "images": []})
            idx += 1

    return result
