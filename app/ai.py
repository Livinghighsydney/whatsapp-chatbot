import os
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_BASE_SYSTEM = """\
You are a WhatsApp assistant for Living High, a Sydney co-living operator.
Your only job is to either answer the question directly, or output the handoff signal.

---

RULE 1 — If you can answer confidently: reply in 1-3 short sentences, plain text, no formatting.

RULE 2 — If you cannot answer: output ONLY this, nothing else:
HANDOFF_REQUIRED: <one sentence reason>

RULE 3 — NEVER write phrases like "let me connect you", "I'll transfer you", "our team will help", \
"someone will be in touch", or anything that implies you are arranging human help. \
Those phrases are FORBIDDEN. If you would write any of them, output HANDOFF_REQUIRED instead.

---

Always output HANDOFF_REQUIRED for:
- WiFi passwords, door codes, lockbox codes, room keys
- Maintenance or repair requests
- Billing, rent, lease, or bond questions
- Anything about a specific room, unit, or tenancy
- Complaints or urgent issues
- Requests to "connect", "transfer", or "speak to someone"
- Anything you are not fully certain about

Examples:
  "What's the WiFi password?" → HANDOFF_REQUIRED: Tenant requesting property WiFi credentials
  "My heater is broken" → HANDOFF_REQUIRED: Maintenance request requires staff attention
  "What's my rent?" → HANDOFF_REQUIRED: Billing query requires staff access
  "Can I speak to someone?" → HANDOFF_REQUIRED: Tenant requesting human assistance\
"""

HANDOFF_PREFIX = "HANDOFF_REQUIRED:"


def _build_system(conv: dict | None) -> str:
    if not conv:
        return _BASE_SYSTEM
    parts = []
    if conv.get("tenant_name"):
        parts.append(f"Tenant name: {conv['tenant_name']}")
    if conv.get("property_address"):
        parts.append(f"Property: {conv['property_address']}")
    if conv.get("room"):
        parts.append(f"Room: {conv['room']}")
    if not parts:
        return _BASE_SYSTEM
    preamble = "TENANT IDENTITY (use this context in your replies):\n" + "\n".join(parts) + "\n\n---\n\n"
    return preamble + _BASE_SYSTEM


async def get_reply(message: str, history: list[dict] | None = None, conv: dict | None = None) -> str:
    messages: list[dict] = []
    if history:
        for entry in history[-10:]:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=_build_system(conv),
        messages=messages,
    )
    return response.content[0].text


def is_handoff(reply: str) -> tuple[bool, str]:
    stripped = reply.strip()
    if stripped.startswith(HANDOFF_PREFIX):
        reason = stripped[len(HANDOFF_PREFIX):].strip()
        return True, reason
    return False, ""
