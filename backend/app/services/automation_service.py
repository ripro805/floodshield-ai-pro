"""Optional n8n webhook integration for incident workflows."""
import httpx

from app.config import N8N_WEBHOOK_URL


async def notify_n8n(event: dict) -> bool:
    if not N8N_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(N8N_WEBHOOK_URL, json=event)
            response.raise_for_status()
            return True
    except httpx.HTTPError:
        return False
