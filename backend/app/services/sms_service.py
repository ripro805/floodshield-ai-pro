"""Twilio SMS delivery through its documented HTTPS API."""
import httpx
from fastapi import HTTPException

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER


async def send_sms(to_number: str, message: str) -> str:
    if not all((TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER)):
        raise HTTPException(
            status_code=503,
            detail="SMS delivery is not configured. Set the Twilio credentials in the backend environment.",
        )

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                data={"To": to_number, "From": TWILIO_FROM_NUMBER, "Body": message},
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            )
            response.raise_for_status()
            return str(response.json().get("sid", "unknown"))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Twilio SMS delivery failed: {exc}") from exc
