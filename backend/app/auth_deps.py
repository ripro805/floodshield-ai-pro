"""
Two dependencies every protected route uses:

    get_current_user   -- decodes the JWT, loads the User from the DB,
                           401s if the token is missing/invalid/expired.
    require_roles(...) -- wraps get_current_user and additionally 403s
                           if the user's role isn't in the allowed set.

Usage in a router:
    @router.post("/recommend", dependencies=[Depends(require_roles(
        UserRole.hospital, UserRole.ngo, UserRole.government,
        UserRole.health_worker, UserRole.admin
    ))])
"""
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth_models import User, UserRole
from app.auth_utils import decode_access_token

# tokenUrl just points Swagger's "Authorize" button at the login route --
# it doesn't change how tokens are actually issued.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None:
        raise credentials_exception

    return user


def require_roles(*allowed_roles: UserRole):
    """Returns a FastAPI dependency that 403s unless current_user.role is allowed."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of these roles: "
                       f"{[r.value for r in allowed_roles]}. Your role: {current_user.role.value}",
            )
        return current_user

    return dependency


# Any authenticated user, regardless of role -- used on the prediction
# endpoints where every role (including citizen) should get early-warning info.
def require_any_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def get_optional_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the authenticated User if valid Bearer token provided, otherwise None."""
    if token is None:
        return None
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return None
    return db.query(User).filter(User.email == payload["sub"]).first()
