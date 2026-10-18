import os
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)


def send_message(to: str, body: str) -> None:
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    message = client.messages.create(
        from_=os.environ["TWILIO_WHATSAPP_NUMBER"],
        to=to,
        body=body,
    )
    logger.info("Twilio message sent | sid=%s", message.sid)
