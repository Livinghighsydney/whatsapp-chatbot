"""Persistent tenant memory — extracts and merges facts from conversation into a JSON blob."""
from __future__ import annotations
import json
import logging
import os
from anthropic import AsyncAnthropic
from app.models.conversation import get_memory, set_memory

logger = logging.getLogger(__name__)
_client: AsyncAnthropic | None = None

_TOOL = {
    "name": "update_memory",
    "description": "Merge new facts learned from the conversation into the tenant memory blob",
    "input_schema": {
        "type": "object",
        "properties": {
            "memory": {
                "type": "object",
                "description": (
                    "Updated memory blob. Keys can be anything meaningful such as "
                    "issues, resolved, pending, preferences, notes. "
                    "Max 10 keys, max 4 items per key. Keep values short (one sentence each)."
                ),
            }
        },
        "required": ["memory"],
    },
}


def _client_() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


async def extract(phone: str, recent: list[dict]) -> None:
    """Background task: extract facts from recent messages and merge into the stored blob."""
    if not recent:
        return
    existing = get_memory(phone)
    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent[-6:]
    )
    try:
        result = await _client_().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            tools=[_TOOL],
            tool_choice={"type": "auto"},
            system=(
                "You extract and maintain a compact memory blob for a tenant chatbot conversation. "
                "Merge any NEW meaningful facts from the recent messages into the existing memory. "
                "Only add facts that are genuinely useful to remember. "
                "Do not repeat what is already in the existing memory. "
                "If nothing new is worth remembering, return the existing memory unchanged."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Existing memory:\n{json.dumps(existing, indent=2)}\n\n"
                    f"Recent conversation:\n{transcript}"
                ),
            }],
        )
        for block in result.content:
            if block.type == "tool_use" and block.name == "update_memory":
                blob = block.input.get("memory", {})
                if isinstance(blob, dict):
                    set_memory(phone, blob)
                    logger.info("Memory updated | phone=%s | keys=%s", phone, list(blob.keys()))
                return
    except Exception:
        logger.warning("Memory extraction failed | phone=%s", phone, exc_info=True)
