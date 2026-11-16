from __future__ import annotations
import logging
import os
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)
_client: AsyncAnthropic | None = None

_TOOL = {
    "name": "save_tenant_info",
    "description": "Save the tenant's identifying details",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Tenant's full name"},
            "property_address": {"type": "string", "description": "Property address (e.g. '42 King St Newtown')"},
            "room": {"type": "string", "description": "Room number (e.g. 'Room 5', '5B')"},
        },
        "required": [],
    },
}


def _client_() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


async def extract_tenant_info(text: str) -> dict:
    try:
        result = await _client_().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            tools=[_TOOL],
            tool_choice={"type": "auto"},
            messages=[{
                "role": "user",
                "content": (
                    "Extract the tenant's name, property address, and room number from "
                    "this message. Only extract what is clearly stated.\n\n"
                    f"Message: {text}"
                ),
            }],
        )
        for block in result.content:
            if block.type == "tool_use" and block.name == "save_tenant_info":
                info = block.input
                return {
                    "name": info.get("name") or None,
                    "property_address": info.get("property_address") or None,
                    "room": info.get("room") or None,
                }
    except Exception:
        logger.exception("Failed to extract tenant info")
    return {"name": None, "property_address": None, "room": None}
