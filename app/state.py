"""In-memory conversation state per tenant.

Resets on process restart — acceptable for MVP. Upgrade to Redis when
running multiple workers or needing persistence across deploys.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Conversation:
    status: Literal["bot_active", "handed_off"] = "bot_active"
    assigned_staff: list[str] = field(default_factory=list)
    handed_off_at: datetime | None = None
    # Role: "user" (tenant), "assistant" (bot), "staff" (human agent)
    history: list[dict] = field(default_factory=list)


_store: dict[str, Conversation] = {}

MAX_HISTORY = 20


def get(phone: str) -> Conversation:
    if phone not in _store:
        _store[phone] = Conversation()
    return _store[phone]


def add_message(phone: str, role: str, content: str) -> None:
    conv = get(phone)
    conv.history.append({"role": role, "content": content})
    if len(conv.history) > MAX_HISTORY:
        conv.history = conv.history[-MAX_HISTORY:]


def find_tenant_for_staff(staff_number: str) -> str | None:
    """Return the tenant number currently assigned to this staff member."""
    for phone, conv in _store.items():
        if conv.status == "handed_off" and staff_number in conv.assigned_staff:
            return phone
    return None
