from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Security
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.schemas import Token
from app.auth.service import login_and_create_token
from app.db.db_manager import get_db
from app.user.models import User as DBUser
from app.user.schemas import User
from app.user.schemas import UserBaseUpdate
from app.user.schemas import UserCreate
from app.user.schemas import UserFullUpdate
from app.user.schemas import UserOut
from app.user.service import create_user
from app.user.service import list_all_users
from app.user.service import update_own_profile
from app.user.service import update_user_by_id


admin_router = APIRouter(prefix="/admin", tags=["admin"])
router = APIRouter(prefix="/users", tags=["users"])


@admin_router.get("/users/", response_model=list[UserFullUpdate])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[DBUser, Security(get_current_active_user, scopes=["admin"])],
    limit: int = 10,
    offset: int = 0,
) -> Any:
    """List users with pagination. Admins only."""
    return await list_all_users(db, limit=limit, offset=offset)


@admin_router.patch("/users/{user_id}", response_model=UserFullUpdate)
async def update_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[DBUser, Security(get_current_active_user, scopes=["admin"])],
    user_id: int,
    user_update: UserFullUpdate,
) -> Any:
    """Update user details by ID. Admins only."""
    return await update_user_by_id(db, user_id, user_update)


@admin_router.get("/status/")
async def read_system_status(
    current_user: Annotated[
        DBUser,
        Security(get_current_active_user, scopes=["admin"]),
    ],
) -> dict[str, Any]:
    """Return system status. Admins only."""
    return {"status": "ok", "user": current_user.username, "is_admin": True}


@router.get("/me", response_model=User)
async def read_users_me(
    current_user: Annotated[
        DBUser,
        Security(get_current_active_user, scopes=["user"]),
    ],
) -> User:
    """Retrieve the profile of the current authenticated user."""
    return User.model_validate(current_user)


@router.put("/me/update", response_model=User, status_code=200)
async def update_own_user(
    user_update: UserBaseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        DBUser,
        Security(get_current_active_user, scopes=["user"]),
    ],
) -> Any:
    """Allow the current user to update their own profile fields."""
    return await update_own_profile(db, current_user, user_update)


@router.post("/register", response_model=UserOut)
async def register_user(
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Register a new user in the system."""
    return await create_user(db, user)


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate user and return JWT access token."""
    return await login_and_create_token(db, form_data.username, form_data.password)
