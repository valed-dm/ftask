"""
FastAPI Dependencies for Authentication and Authorization.

This module provides dependency functions used in API endpoints to secure
access by validating JWTs, fetching the current user, and checking
authorization scopes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Security
from fastapi import status
from fastapi.security import SecurityScopes
import jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import TokenData
from app.auth.schemas import oauth2_scheme
from app.core.config import settings
from app.db.db_manager import get_db
from app.user import repository
from app.user.models import User


def _user_has_all_required_scopes(
    user_scopes: set[str], required_scopes: set[str]
) -> bool:
    """
    Checks if the user possesses ALL the scopes required.
    """
    return required_scopes.issubset(user_scopes)


def _user_has_any_required_scope(
    user_scopes: set[str], required_scopes: set[str]
) -> bool:
    """
    Checks if the user possesses AT LEAST ONE of the scopes required.
    """
    return bool(required_scopes.intersection(user_scopes))


# --- Main Application Logic ---
# Select the desired authorization strategy for the application.
# To change the model, simply change which function is imported here.
_check_scopes = _user_has_any_required_scope


async def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Main security dependency to decode and validate a JWT access token.

    This function performs the following checks:
    1. Decodes the JWT.
    2. Validates the token payload has a subject (username).
    3. Fetches the user from the database.
    4. Checks if the token's scopes are sufficient for the endpoint's requirements.

    Args:
        security_scopes: The security scopes required for the endpoint.
        token: The bearer token from the Authorization header.
        db: The SQLAlchemy asynchronous session.

    Raises:
        HTTPException (401): If authentication fails at any step.
        HTTPException (403): If the token scopes are insufficient.

    Returns:
        The authenticated User model instance.
    """
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str | None = payload.get("sub")
        if not username:
            raise credentials_exception
        token_data = TokenData(scopes=payload.get("scopes", ""), username=username)

    except (jwt.InvalidTokenError, ValidationError) as e:
        raise credentials_exception from e

    user = await repository.get_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    if security_scopes.scopes:
        token_scopes = set(token_data.scopes.split())
        required_scopes = set(security_scopes.scopes)

        # Use the selected authorization utility function.
        if not _check_scopes(
            user_scopes=token_scopes,
            required_scopes=required_scopes,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user


def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=[])],
) -> User:
    """
    A composable dependency to ensure the authenticated user is active.

    This should be used in most endpoints to prevent disabled users from
    performing actions. It builds upon `get_current_user`.
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")

    return current_user
