from __future__ import annotations
import logging
import os
import httpx

logger = logging.getLogger(__name__)

_phone_number_id: str | None = None
_GRAPH = "https://graph.facebook.com/v19.0"


def set_phone_number_id(pid: str) -> None:
    global _phone_number_id
    if _phone_number_id != pid:
        logger.info("Phone number ID detected from webhook: %s", pid)
        _phone_number_id = pid


def _pid() -> str:
    return _phone_number_id or os.environ["META_PHONE_NUMBER_ID"]


def _post(payload: dict) -> None:
    token = os.environ["META_ACCESS_TOKEN"]
    resp = httpx.post(
        f"{_GRAPH}/{_pid()}/messages",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    if not resp.is_success:
        logger.error("Meta API error | %s | %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _clean(to: str) -> str:
    return to.replace("whatsapp:", "").replace("+", "")


def send_text(to: str, body: str) -> None:
    _post({"messaging_product": "whatsapp", "to": _clean(to), "type": "text", "text": {"body": body}})
    logger.info("Sent text | to=%s", _clean(to))


def send_template(to: str, template_name: str, variables: list[str], language: str = "en") -> None:
    _post({
        "messaging_product": "whatsapp",
        "to": _clean(to),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": v} for v in variables]}],
        },
    })


def send_media(to: str, media_id: str, media_type: str) -> None:
    _post({
        "messaging_product": "whatsapp",
        "to": _clean(to),
        "type": media_type,
        media_type: {"id": media_id},
    })


def send_image_url(to: str, url: str, caption: str = "") -> None:
    payload: dict = {"messaging_product": "whatsapp", "to": _clean(to), "type": "image", "image": {"link": url}}
    if caption:
        payload["image"]["caption"] = caption
    _post(payload)
    logger.info("Sent image | to=%s | caption=%s", _clean(to), caption[:50])


def mark_read_typing(message_id: str) -> None:
    _post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id, "typing_indicator": {"type": "text"}})


def classify_media(content_type: str) -> str:
    if content_type.startswith("image/"): return "image"
    if content_type.startswith("video/"): return "video"
    if content_type.startswith("audio/"): return "audio"
    return "document"


async def upload_media(content: bytes, content_type: str, filename: str) -> str:
    token = os.environ["META_ACCESS_TOKEN"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GRAPH}/{_pid()}/media",
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": content_type},
            files={"file": (filename, content, content_type)},
            timeout=30,
        )
        if not resp.is_success:
            logger.error("Media upload failed | %s | %s", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()["id"]
