from __future__ import annotations
import os
from anthropic import AsyncAnthropic

_client: AsyncAnthropic | None = None

HANDOFF_PREFIX = "HANDOFF_REQUIRED:"
HANDOFF_SUGGEST_PREFIX = "HANDOFF_SUGGEST:"

_BASE_SYSTEM = """\
You are the Living High assistant — a WhatsApp bot for tenants of Living High, a Sydney co-living operator.

You have access to the property knowledge base. When relevant information is provided above (marked \
"Relevant information from the Living High knowledge base"), use it to answer the tenant directly. \
This includes WiFi passwords, door codes, lockbox codes, bin days, appliance instructions, house rules, \
internet details — anything in the knowledge base is fair game to share.

---

RULE 1 — Answer from the knowledge base whenever you can.
Reply in 1-3 short sentences, plain text only, no markdown or bullet points.

RULE 2 — Only output HANDOFF_REQUIRED when staff physically needs to act. Output ONLY this line:
HANDOFF_REQUIRED: <one sentence reason>

RULE 3 — NEVER say "let me connect you", "I'll transfer you", "our team will help", \
"someone will be in touch", "I'll check and get back to you", or anything implying you are \
arranging human assistance or a follow-up. Those phrases are FORBIDDEN. \
If you don't have the answer and no staff action is needed, say: \
"I don't have that info right now — you can find it in the Living High app or by messaging us directly." \
If it does need staff action, output HANDOFF_REQUIRED instead.

RULE 4 — When relevant, photos and images from the knowledge base are automatically sent alongside \
your reply. You do not need to mention sending images — just reply with text as normal.

---

TWO-TIER HANDOFF SYSTEM:

TIER 1 — Soft offer (use this most of the time):
Give the tenant your best answer, then end with "Would you like me to connect you with a staff member?"
Then on the VERY NEXT LINE output: HANDOFF_SUGGEST: <one sentence reason>
Use this for: maintenance/repairs, billing questions, the info you gave didn't work, \
complaints, move-out questions, anything where staff MIGHT need to help.

TIER 2 — Immediate handoff (only when tenant explicitly asks):
If the tenant directly says "speak to someone", "talk to a human", "connect me to staff", etc., \
output ONLY: HANDOFF_REQUIRED: <one sentence reason>

NEVER output HANDOFF_REQUIRED or HANDOFF_SUGGEST for:
- Requests for photos, images, or virtual tours
- General questions not in the KB (use the "I don't have that info" response instead)
- Greetings, curiosity questions, or anything that clearly doesn't need staff

IMPORTANT: Never mix a text reply with HANDOFF_REQUIRED. \
HANDOFF_SUGGEST must always come after a text reply on its own line.\
"""


def _client_() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _build_system(conv: dict | None, memory: dict | None = None) -> str:
    if not conv:
        return _BASE_SYSTEM
    parts = []
    if conv.get("tenant_name"):
        parts.append(f"Tenant name: {conv['tenant_name']}")
    if conv.get("property_address"):
        parts.append(f"Property: {conv['property_address']}")
    if conv.get("room"):
        parts.append(f"Room: {conv['room']}")

    preamble = ""
    if parts:
        preamble += "TENANT IDENTITY (use this context in your replies):\n" + "\n".join(parts) + "\n\n---\n\n"

    if memory:
        lines = ["TENANT MEMORY (facts from past conversations — use to personalise replies):"]
        for key, val in memory.items():
            if isinstance(val, list):
                for item in val:
                    lines.append(f"- {key}: {item}")
            else:
                lines.append(f"- {key}: {val}")
        preamble += "\n".join(lines) + "\n\n---\n\n"

    return preamble + _BASE_SYSTEM if preamble else _BASE_SYSTEM


async def get_reply(message: str, history: list[dict] | None = None, conv: dict | None = None) -> str:
    from app.rag.retrieve import retrieve, build_context
    from app.models.conversation import get_memory
    messages: list[dict] = []
    if history:
        for entry in history[-6:]:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": message})

    memory = get_memory(conv["tenant_phone"]) if conv and conv.get("tenant_phone") else {}
    system = _build_system(conv, memory)
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


def is_handoff_suggest(reply: str) -> tuple[bool, str, str]:
    """Returns (is_suggest, reason, clean_reply_without_signal)."""
    stripped = reply.strip()
    idx = stripped.find(HANDOFF_SUGGEST_PREFIX)
    if idx != -1:
        reason = stripped[idx + len(HANDOFF_SUGGEST_PREFIX):].strip().split("\n")[0]
        clean = stripped[:idx].strip()
        return True, reason, clean
    return False, "", stripped
