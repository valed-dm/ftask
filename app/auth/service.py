"""
Service Layer for Authentication Business Logic.

This module provides the core logic for user login and token generation.
"""

from datetime import timedelta

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth
from app.auth.schemas import Token
from app.core.config import settings
from app.user.service import authenticate_user


async def login_and_create_token(
    db: AsyncSession,
    username: str,
    password: str,
) -> Token:
    """
    Orchestrates the user login process.

    1. Authenticates the user's credentials via the user service.
    2. Creates a JWT access token if authentication is successful.

    Args:
        db: The SQLAlchemy asynchronous session.
        username: The username to authenticate.
        password: The plain-text password to verify.

    Raises:
        HTTPException (401): If authentication fails due to incorrect credentials.

    Returns:
        A Pydantic Token schema containing the new access token.
    """
    user = await authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=expires_delta,
    )

    return Token(access_token=access_token, token_type=settings.TOKEN_TYPE)
