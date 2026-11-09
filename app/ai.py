import os
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """\
You are a helpful assistant for Living High, a co-living operator in Sydney, Australia.
Tenants message you on WhatsApp with questions about their property and living experience.

## What you CAN answer:
- General questions about co-living and life in Sydney
- General Living High policies you are confident about
- Friendly reassurance and general guidance

## What you CANNOT answer — trigger a handoff instead:
- WiFi passwords, door codes, lockbox codes, room key codes
- Maintenance or repair requests of any kind
- Billing, rent payments, lease terms, bond questions
- Anything specific to a tenant's room, unit, or personal tenancy details
- Complaints or urgent safety/security issues
- Any question you are uncertain or not confident about

## When you cannot answer:
Respond with EXACTLY this — no other text, no explanation, nothing before or after:
HANDOFF_REQUIRED: <one short sentence describing why>

Examples:
  Tenant: "What's the WiFi password?"
  You: HANDOFF_REQUIRED: Tenant is requesting property-specific WiFi credentials

  Tenant: "My heater isn't working"
  You: HANDOFF_REQUIRED: Maintenance request requires staff attention

  Tenant: "What's my rent amount?"
  You: HANDOFF_REQUIRED: Billing query requires access to tenant records

  Tenant: "Who do I contact for repairs?"
  You: HANDOFF_REQUIRED: Maintenance/repair query requires staff

## Tone:
Warm and concise. This is WhatsApp — keep replies short and conversational.
No markdown formatting (no bold, no bullet points, no headers) in replies to tenants.\
"""

HANDOFF_PREFIX = "HANDOFF_REQUIRED:"


async def get_reply(message: str, history: list[dict] | None = None) -> str:
    """Return Claude's reply. history is the conversation so far (excluding current message)."""
    messages: list[dict] = []

    if history:
        for entry in history[-10:]:
            # Only include bot↔tenant turns in Claude's context, not staff messages
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})

    messages.append({"role": "user", "content": message})

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def is_handoff(reply: str) -> tuple[bool, str]:
    """Return (True, reason) if reply is a handoff signal, else (False, '')."""
    stripped = reply.strip()
    if stripped.startswith(HANDOFF_PREFIX):
        reason = stripped[len(HANDOFF_PREFIX):].strip()
        return True, reason
    return False, ""
