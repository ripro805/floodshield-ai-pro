"""
/auth/signup -- create an account with a role
/auth/login  -- exchange email+password for a JWT access token
 /auth/forgot-password -- request a short-lived password reset token
 /auth/reset-password  -- set a new password using that token
 /auth/me     -- return the currently authenticated user (handy for the
                frontend to check "who am I / what role am I" after login)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth_models import User, UserRole
from app.auth_schemas import (
    UserSignup, UserLogin, UserOut, Token,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest,
)
from app.auth_utils import hash_password, verify_password, create_access_token
from app.auth_utils import decode_access_token
from app.auth_deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        district=payload.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email, "role": user.role.value})
    return Token(access_token=token, user=_to_user_out(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"sub": user.email, "role": user.role.value})
    return Token(access_token=token, user=_to_user_out(user))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Issue a short-lived reset token without disclosing account existence."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        return ForgotPasswordResponse(
            message="If an account exists for that email, reset instructions have been prepared."
        )

    token = create_access_token(
        {"sub": user.email, "purpose": "password_reset"},
        expires_minutes=30,
    )
    return ForgotPasswordResponse(
        message="If an account exists for that email, reset instructions have been prepared.",
        reset_token=token,
    )


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_data = decode_access_token(payload.token)
    if not token_data or token_data.get("purpose") != "password_reset" or not token_data.get("sub"):
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")

    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if user is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Your password has been reset successfully."}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return _to_user_out(current_user)


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, full_name=user.full_name,
        role=user.role, district=user.district,
    )


class PromoteMeRequest(BaseModel):
    """One-time bootstrap body.

    The client sends the BOOTSTRAP_TOKEN the deployer shared with them.
    The server compares it against the env var; the role is then flipped
    to admin on the *currently authenticated* user.
    """
    bootstrap_token: str



@router.post("/promote-me", response_model=Token)
def promote_me_to_admin(
    payload: PromoteMeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One-time bootstrap: any authenticated user can become the first admin.

    Disabled when:
      - BOOTSTRAP_TOKEN env var is empty
      - any admin already exists in the DB
      - the supplied token does not match the env var
    On success, the caller's role is set to admin and a fresh token is
    issued so the next request reflects the new role.
    """
    from app.config import BOOTSTRAP_TOKEN

    if not BOOTSTRAP_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Bootstrap is disabled on this server. Ask an existing admin to promote you via /admin/users.",
        )

    if payload.bootstrap_token != BOOTSTRAP_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Bootstrap token is incorrect.",
        )

    existing_admin = (
        db.query(User)
        .filter(User.role == UserRole.admin, User.id != current_user.id)
        .first()
    )
    if existing_admin is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bootstrap is single-use: an admin already exists "
                f"({existing_admin.email}). Ask them to use the Admin Panel "
                f"to grant your account a higher role."
            ),
        )

    current_user.role = UserRole.admin
    db.commit()
    db.refresh(current_user)

    # Re-issue the JWT so the new role is visible in subsequent calls.
    fresh_token = create_access_token(
        {"sub": current_user.email, "role": current_user.role.value}
    )

    return {
        "access_token": fresh_token,
        "token_type": "bearer",
        "user": _to_user_out(current_user),
    }



@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)):
    """Public read: is the one-time admin bootstrap available?

    Returns:
      enabled:        True iff BOOTSTRAP_TOKEN is set in the environment.
      admin_exists:   True iff at least one user with role=admin is in the DB.
      usable:         True iff enabled AND not admin_exists.

    The frontend hides the "Promote me to admin" button unless `usable`,
    so a stale UI doesn't see misleading errors.
    """
    from app.config import BOOTSTRAP_TOKEN
    from app.auth_models import UserRole

    enabled = bool(BOOTSTRAP_TOKEN)
    admin_count = (
        db.query(User).filter(User.role == UserRole.admin).count()
    )
    admin_exists = admin_count > 0
    return {
        "enabled": enabled,
        "admin_exists": admin_exists,
        "admin_count": admin_count,
        "usable": enabled and not admin_exists,
    }



@router.post("/demote-me", response_model=Token)
def demote_me_to_citizen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-demote: turn my own admin account back into a citizen.

    Useful as the "undo" for /auth/promote-me: if the deployer
    bootstrapped the wrong account, they can demote it and bootstrap
    again (assuming the single-use guard is reset by a fresh
    BOOTSTRAP_TOKEN, or by wiping the existing admin manually).

    Safety: refuses to demote if the caller is the only admin in the
    database.  At least one admin must remain so the system can be
    managed.

    Returns a fresh JWT with the new (citizen) role so the next
    request reflects it.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=400,
            detail="You are not currently an admin -- nothing to demote.",
        )

    # Count other admins (excluding self).  Refuse if I'm the only one.
    other_admin_count = (
        db.query(User)
        .filter(User.role == UserRole.admin, User.id != current_user.id)
        .count()
    )
    if other_admin_count == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "You are the only admin in the database. Promote another "
                "user to admin (via /admin/users or /auth/promote-me) "
                "before demoting yourself, otherwise no one will be able "
                "to manage the system."
            ),
        )

    current_user.role = UserRole.citizen
    db.commit()
    db.refresh(current_user)

    fresh_token = create_access_token(
        {"sub": current_user.email, "role": current_user.role.value}
    )
    return {
        "access_token": fresh_token,
        "token_type": "bearer",
        "user": _to_user_out(current_user),
    }
