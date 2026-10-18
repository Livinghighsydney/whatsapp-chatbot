import os
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = (
    "You are a helpful assistant for Living High, a co-living operator in Sydney, Australia. "
    "You help tenants with questions about their property, building facilities, and living arrangements. "
    "Be friendly, concise, and helpful. "
    "If you don't know something specific about a tenant's property, say so honestly and suggest they contact the Living High team."
)


async def get_reply(message: str) -> str:
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    return response.content[0].text
