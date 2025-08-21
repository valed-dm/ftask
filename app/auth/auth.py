"""
Core Authentication Utilities.

This module provides essential security functions for password
hashing/verification (using bcrypt) and JWT access token creation.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies if a plain-text password matches a bcrypt-hashed password.

    Args:
        plain_password: The plain-text password to check.
        hashed_password: The hashed password from the database.

    Returns:
        True if the passwords match, False otherwise.
    """
    plain_password_bytes = plain_password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.

    Args:
        password: The plain-text password to hash.

    Returns:
        The resulting bcrypt hash as a string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """
    Creates a new JWT access token.

    Args:
        data: The payload data to encode in the token (e.g., user identifier).
        expires_delta: Optional timedelta for token expiration. If not provided,
                       a default expiration from settings is used.

    Returns:
        The encoded JWT access token as a string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
