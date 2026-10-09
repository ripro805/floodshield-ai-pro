"""SMS alert subscriptions and Twilio-backed delivery."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user, require_roles
from app.auth_models import User, UserRole
from app.database import get_db
from app.schemas import SmsAlertRequest, SmsSubscriptionRequest, SmsSubscriptionResponse
from app.services.sms_service import send_sms
from app.sms_models import SmsSubscription

router = APIRouter(prefix="/alerts/sms", tags=["SMS Alerts"])
OPERATIONAL_ROLES = (
    UserRole.health_worker, UserRole.hospital, UserRole.ngo,
    UserRole.government, UserRole.admin,
)
_RISK_ORDER = {"Medium": 1, "High": 2, "Critical": 3}


def _response(subscription: SmsSubscription) -> SmsSubscriptionResponse:
    return SmsSubscriptionResponse(
        phone_number=subscription.phone_number,
        district=subscription.district,
        risk_threshold=subscription.risk_threshold,
        is_active=subscription.is_active,
    )


@router.get("/subscription", response_model=SmsSubscriptionResponse | None)
def get_subscription(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    subscription = db.query(SmsSubscription).filter(SmsSubscription.user_id == current_user.id).first()
    return _response(subscription) if subscription else None


@router.post("/subscribe", response_model=SmsSubscriptionResponse)
def subscribe(
    payload: SmsSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = db.query(SmsSubscription).filter(SmsSubscription.user_id == current_user.id).first()
    if subscription is None:
        subscription = SmsSubscription(user_id=current_user.id)
        db.add(subscription)
    subscription.phone_number = payload.phone_number
    subscription.district = payload.district
    subscription.risk_threshold = payload.risk_threshold
    subscription.is_active = True
    subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(subscription)
    return _response(subscription)


@router.delete("/unsubscribe")
def unsubscribe(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscription = db.query(SmsSubscription).filter(SmsSubscription.user_id == current_user.id).first()
    if subscription:
        subscription.is_active = False
        subscription.updated_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "unsubscribed"}


@router.post("/send", dependencies=[Depends(require_roles(*OPERATIONAL_ROLES))])
async def send_alert(
    payload: SmsAlertRequest,
    db: Session = Depends(get_db),
):
    if payload.risk_level not in _RISK_ORDER:
        raise HTTPException(status_code=422, detail="Unsupported risk level")

    subscriptions = db.query(SmsSubscription).filter(SmsSubscription.is_active.is_(True)).all()
    matching = [
        item for item in subscriptions
        if (not item.district or item.district.casefold() == payload.district.casefold())
        and _RISK_ORDER[payload.risk_level] >= _RISK_ORDER[item.risk_threshold]
    ]
    message = payload.message or (
        f"FloodShield alert: {payload.district} is at {payload.risk_level} risk. "
        "Check the dashboard and follow local safety guidance."
    )
    message_ids = [await send_sms(item.phone_number, message) for item in matching]
    return {"district": payload.district, "risk_level": payload.risk_level, "sent_count": len(message_ids), "message_ids": message_ids}
