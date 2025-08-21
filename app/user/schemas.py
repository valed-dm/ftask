"""
Pydantic Schemas for User Management.

This module defines the data structures for creating, reading, and updating
user data, ensuring type validation and serialization.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr


class User(BaseModel):
    """Base Pydantic model for a User, containing shared fields."""

    username: str
    email: EmailStr | None = None
    full_name: str | None = None
    disabled: bool = False
    scopes: str

    model_config = ConfigDict(from_attributes=True)


class UserCreate(User):
    """Schema for creating a new user, requires a password."""

    password: str


class UserOut(User):
    """Schema for returning a user to the client, includes the database ID."""

    id: int


class UserBaseUpdate(BaseModel):
    """Schema for a standard user updating their own profile information."""

    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserFullUpdate(UserBaseUpdate):
    """Schema for an admin performing a full update on a user's profile."""

    disabled: bool | None = None
    scopes: str | None = None
