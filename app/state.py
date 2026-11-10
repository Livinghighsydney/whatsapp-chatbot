"""In-memory conversation state per tenant.

Resets on process restart — acceptable for MVP. Upgrade to Redis when
running multiple workers or needing persistence across deploys.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class TenantInfo:
    name: str = ""
    property_address: str = ""
    room: str = ""

    def display(self, phone: str) -> str:
        """Human-readable label for use in staff notifications."""
        parts = [p for p in (self.name, self.property_address, self.room) if p]
        return " | ".join(parts) if parts else f"+{phone}"


@dataclass
class Conversation:
    # State machine: bot_active → collecting_info → handed_off → bot_active
    status: Literal["bot_active", "collecting_info", "handed_off"] = "bot_active"

    # Populated during collecting_info, persisted for the lifetime of the session
    tenant_info: TenantInfo = field(default_factory=TenantInfo)

    # Reason captured when bot first detects it needs to hand off
    handoff_reason: str = ""

    # Short ID assigned at handoff (T1, T2…) used in DONE commands
    session_id: str = ""

    assigned_staff: list[str] = field(default_factory=list)
    handed_off_at: datetime | None = None

    # Chronological message log — roles: "user", "assistant", "staff"
    history: list[dict] = field(default_factory=list)

    # Tracks which staff numbers have already received the initial history brief
    staff_history_sent: set = field(default_factory=set)


# ── Store ──────────────────────────────────────────────────────────────────────

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


# ── Session registry ───────────────────────────────────────────────────────────
# Maps short session IDs (T1, T2…) → tenant phone numbers so staff can type
# "DONE T1" rather than a full phone number.

_session_counter: int = 0
_session_map: dict[str, str] = {}  # session_id → tenant_phone


def new_session(phone: str) -> str:
    global _session_counter
    _session_counter += 1
    sid = f"T{_session_counter}"
    _session_map[sid] = phone
    return sid


def find_tenant_by_session(session_id: str) -> str | None:
    return _session_map.get(session_id.upper())


# ── Queries ────────────────────────────────────────────────────────────────────

def find_active_handoffs_for_staff(staff_number: str) -> list[tuple[str, Conversation]]:
    """Return all (phone, conversation) pairs currently handed off to this staff member."""
    return [
        (phone, conv)
        for phone, conv in _store.items()
        if conv.status == "handed_off" and staff_number in conv.assigned_staff
    ]


# ── Mutations ──────────────────────────────────────────────────────────────────

def resolve(phone: str) -> None:
    """Reset a handed-off conversation back to bot control."""
    conv = get(phone)
    _session_map.pop(conv.session_id, None)
    conv.status = "bot_active"
    conv.session_id = ""
    conv.assigned_staff = []
    conv.handed_off_at = None
    conv.staff_history_sent = set()
    conv.handoff_reason = ""
    # Intentionally keep tenant_info — avoids re-asking if they message again
