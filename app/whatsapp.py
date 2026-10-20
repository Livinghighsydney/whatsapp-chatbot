import os
import logging
import httpx

logger = logging.getLogger(__name__)


def send_message(to: str, body: str) -> None:
    phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    # Meta expects plain number without whatsapp: prefix
    to_clean = to.replace("whatsapp:", "").replace("+", "")

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "text",
        "text": {"body": body},
    }

    response = httpx.post(url, json=payload, headers=headers)
    response.raise_for_status()
    logger.info("Meta message sent | to=%s | status=%s", to_clean, response.status_code)
