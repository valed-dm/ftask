"""
Pydantic Schemas for Authentication.

This module defines the data structures for handling OAuth2 tokens,
including the response model for the token endpoint and the data
encoded within the JWT.
"""

from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import settings


# OAuth2 scheme definition.
# The tokenUrl points to the endpoint where the client can fetch a token.
# auto_error=False means the dependency won't raise an error if the
# Authorization header is missing, allowing for optional authentication.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token", auto_error=False)


class Token(BaseModel):
    """Schema for the access token response provided upon successful login."""

    access_token: str
    token_type: str = settings.TOKEN_TYPE


class TokenData(BaseModel):
    """Schema representing the data stored inside the JWT access token."""

    username: str | None = None
    scopes: str = ""
