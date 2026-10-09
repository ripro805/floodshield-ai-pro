"""Optional local/cloud chatbot providers with safe fallback behavior."""
import httpx

from app.config import HF_INFERENCE_API_URL, HF_INFERENCE_TOKEN, OLLAMA_BASE_URL, OLLAMA_MODEL


async def generate_ollama(messages: list[dict]) -> str | None:
    if not OLLAMA_BASE_URL or not OLLAMA_MODEL:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content") or None
    except (httpx.HTTPError, ValueError):
        return None


async def generate_huggingface(prompt: str) -> str | None:
    if not HF_INFERENCE_API_URL or not HF_INFERENCE_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                HF_INFERENCE_API_URL,
                headers={"Authorization": f"Bearer {HF_INFERENCE_TOKEN}"},
                json={"inputs": prompt, "parameters": {"max_new_tokens": 512}},
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return payload[0].get("generated_text")
            return None
    except (httpx.HTTPError, ValueError):
        return None
