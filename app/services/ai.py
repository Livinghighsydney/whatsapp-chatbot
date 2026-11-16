from __future__ import annotations
import os
from anthropic import AsyncAnthropic

_client: AsyncAnthropic | None = None

HANDOFF_PREFIX = "HANDOFF_REQUIRED:"

_BASE_SYSTEM = """\
You are the Living High assistant — a WhatsApp bot for tenants of Living High, a Sydney co-living operator.

You have access to the property knowledge base. When relevant information is provided above (marked \
"Relevant information from the Living High knowledge base"), use it to answer the tenant directly. \
This includes WiFi passwords, door codes, lockbox codes, bin days, appliance instructions, house rules, \
internet details — anything in the knowledge base is fair game to share.

---

RULE 1 — Answer from the knowledge base whenever you can.
Reply in 1-3 short sentences, plain text only, no markdown or bullet points.

RULE 2 — If the tenant says something isn't working, tried your answer and it failed, or the issue \
needs physical action from staff, output ONLY this:
HANDOFF_REQUIRED: <one sentence reason>

RULE 3 — NEVER say "let me connect you", "I'll transfer you", "our team will help", \
"someone will be in touch", "I'll check and get back to you", or anything implying you are \
arranging human assistance or a follow-up. Those phrases are FORBIDDEN. \
If you don't have the answer and it doesn't need staff action, say: \
"I don't have that info right now — you can find it in the Living High app or by messaging us directly." \
If it does need staff action, output HANDOFF_REQUIRED instead.

---

Output HANDOFF_REQUIRED for:
- Maintenance, repairs, or anything physically broken
- Rent, billing, bond, lease, or payment questions
- Tenant explicitly asks to speak to a person
- Tenant says the info you gave didn't work or the issue persists
- Complaints about other tenants, noise, or safety
- Move-out, end of tenancy, or lease renewal
- The answer is not in the knowledge base above and requires staff action

IMPORTANT: Never mix a text reply with HANDOFF_REQUIRED. Output one or the other, never both.\
"""


def _client_() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


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
    from app.rag.retrieve import retrieve, build_context
    messages: list[dict] = []
    if history:
        for entry in history[-10:]:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": message})

    system = _build_system(conv)
    if conv:
        chunks = retrieve(message, property_address=conv.get("property_address"),
                          room_number=conv.get("room"))
        ctx = build_context(chunks)
        if ctx:
            system = ctx + "\n\n---\n\n" + system

    response = await _client_().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def is_handoff(reply: str) -> tuple[bool, str]:
    stripped = reply.strip()
    idx = stripped.find(HANDOFF_PREFIX)
    if idx != -1:
        return True, stripped[idx + len(HANDOFF_PREFIX):].strip().split("\n")[0]
    return False, ""
