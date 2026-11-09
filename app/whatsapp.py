import os
import logging
import httpx

logger = logging.getLogger(__name__)


def _post(payload: dict) -> None:
    phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
    token = os.environ["META_ACCESS_TOKEN"]
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = httpx.post(url, json=payload, headers=headers)
    response.raise_for_status()


def send_message(to: str, body: str) -> None:
    to_clean = to.replace("whatsapp:", "").replace("+", "")
    _post({
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "text",
        "text": {"body": body},
    })
    logger.info("Meta message sent | to=%s", to_clean)


def send_template(to: str, template_name: str, variables: list[str], language: str = "en_US") -> None:
    to_clean = to.replace("whatsapp:", "").replace("+", "")
    _post({
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in variables],
                }
            ],
        },
    })
    logger.info("Template sent | to=%s | template=%s", to_clean, template_name)


def mark_read_and_typing(message_id: str) -> None:
    """Mark incoming message as read and show typing indicator.

    Sends a single API call that:
    - Shows double blue ticks to the sender (read receipt)
    - Shows the three-dot typing animation while the bot prepares a reply

    The typing indicator is dismissed automatically when the reply is sent,
    or after 25 seconds if no reply arrives.
    """
    _post({
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    })
    logger.debug("Read + typing sent | message_id=%s", message_id)
