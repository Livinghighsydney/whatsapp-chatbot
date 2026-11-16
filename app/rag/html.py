from __future__ import annotations
import re
from bs4 import BeautifulSoup, Tag

_ROOM_RE = re.compile(r"\bRoom\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)
_SHARED_KEYWORDS = {
    "kitchen", "laundry", "bathroom", "shower", "hallway", "living room",
    "backyard", "balcony", "sunroom", "car park", "parking", "lobby",
    "common area", "outdoor", "garden", "rooftop",
}


def clean(html: str) -> tuple[str, list[str]]:
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


def extract_heading_images(html: str) -> list[dict]:
    """
    Returns [{src, caption}] for every heading+image pair in the HTML.
    A pair is: a <p> with a <strong> (or h1-h4) followed immediately by a <p> with only an <img>.
    Only images with a non-empty caption are returned.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    last_heading: str = ""

    for el in soup.find_all(["h1", "h2", "h3", "h4", "p"]):
        if not isinstance(el, Tag):
            continue
        # Check if this element is a heading
        if el.name in ("h1", "h2", "h3", "h4"):
            text = el.get_text(" ", strip=True)
            if text:
                last_heading = text
            continue
        # <p> containing a <strong> (and no img) → treat as heading
        has_strong = el.find("strong")
        has_img = el.find("img")
        if has_strong and not has_img:
            text = el.get_text(" ", strip=True)
            if text:
                last_heading = text
            continue
        # <p> containing only an <img> → image paragraph
        if has_img and not el.get_text(strip=True):
            src = has_img.get("src", "")
            # Fall back to alt text as caption if no heading found
            caption = last_heading or has_img.get("alt", "")
            if src and caption:
                results.append({"src": src, "caption": caption})
            last_heading = ""  # consume the heading
    return results


def room_from_alt(alt: str) -> str | None:
    lower = alt.lower().strip()
    if any(kw in lower for kw in _SHARED_KEYWORDS):
        return None
    m = _ROOM_RE.search(alt)
    return m.group(1) if m else None


def dominant_room(text: str) -> str | None:
    rooms = set(_ROOM_RE.findall(text))
    return rooms.pop() if len(rooms) == 1 else None
