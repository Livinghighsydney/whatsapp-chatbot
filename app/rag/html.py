from __future__ import annotations
import re
from bs4 import BeautifulSoup

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


def room_from_alt(alt: str) -> str | None:
    lower = alt.lower().strip()
    if any(kw in lower for kw in _SHARED_KEYWORDS):
        return None
    m = _ROOM_RE.search(alt)
    return m.group(1) if m else None


def dominant_room(text: str) -> str | None:
    rooms = set(_ROOM_RE.findall(text))
    return rooms.pop() if len(rooms) == 1 else None
