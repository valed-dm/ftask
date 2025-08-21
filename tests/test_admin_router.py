from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import User


async def test_read_system_status(
    async_client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Test a successful request to the /status/ endpoint using a valid admin token.
    Covers the `read_system_status` function.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.get("/admin/status/", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["user"] == "admin"  # From the admin_user fixture
    assert data["is_admin"] is True


async def test_list_users(
    async_client: AsyncClient, admin_token: str, regular_users: list[User]
) -> None:
    """
    Test a successful request to list user with default pagination.
    Covers the main success path of `list_users`.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.get("/admin/users/", headers=headers)

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4
    assert data[0]["username"] == "admin"
    assert data[2]["username"] == "user2"


async def test_list_users_with_pagination(
    async_client: AsyncClient, admin_token: str, regular_users: list[User]
) -> None:
    """
    Test listing user with limit and offset query parameters.
    Covers the limit/offset logic in the `list_users` function.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Get the second user by skipping 1 and limiting to 1
    response = await async_client.get("/admin/users/?limit=1&offset=2", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["username"] == "user2"


async def test_update_user(
    async_client: AsyncClient,
    raw_db_session: AsyncSession,  # Use the independent session for verification
    admin_token: str,
    regular_users: list[User],
) -> None:
    user_to_update = regular_users[0]
    user_id_to_check = user_to_update.id
    update_data = {
        "full_name": "New Updated Name",
        "disabled": True,
        "email": "new.email@example.com",
        "username": "user1",
        "scopes": "user updated",
    }

    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.patch(
        f"/admin/users/{user_to_update.id}", json=update_data, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "New Updated Name"

    updated_user_in_db = await raw_db_session.get(User, user_id_to_check)

    assert updated_user_in_db is not None
    assert updated_user_in_db.full_name == "New Updated Name"
    assert updated_user_in_db.disabled is True
    assert updated_user_in_db.scopes == "user updated"


async def test_update_user_not_found(
    async_client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Test updating a user that does not exist.
    Covers the HTTPException 404 branch in `update_user`.
    """
    non_existent_user_id = 9999
    update_data = {
        "full_name": "Ghost User",
        "disabled": False,
        "email": "ghost@example.com",
        "username": "ghost",
        "scopes": "none",
    }

    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await async_client.patch(
        f"/admin/users/{non_existent_user_id}", json=update_data, headers=headers
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"] == f"User with ID {non_existent_user_id} not found."
    )


@pytest.mark.parametrize(
    "path",
    [
        "/admin/status/",
        "/admin/users/",
    ],
)
async def test_admin_routes_unauthorized_for_regular_user(
    async_client: AsyncClient, user_a_token: str, path: str
) -> None:
    """
    Tests that a regular, non-admin user receives a 403 Forbidden error
    when trying to access any admin-only GET endpoint.
    """
    headers = {"Authorization": f"Bearer {user_a_token}"}
    response = await async_client.get(path, headers=headers)

    # The user is authenticated, but not authorized for this scope.
    # Therefore, the correct status code is 403 Forbidden.
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


async def test_admin_patch_unauthorized_for_regular_user(
    async_client: AsyncClient, user_a_token: str, regular_users: list[User]
) -> None:
    """
    Tests that a regular, non-admin user receives a 403 Forbidden error
    when trying to access the admin-only PATCH endpoint.
    """
    user_to_update = regular_users[0]
    update_data = {"full_name": "Attempted Update"}

    headers = {"Authorization": f"Bearer {user_a_token}"}
    response = await async_client.patch(
        f"/admin/users/{user_to_update.id}", json=update_data, headers=headers
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
