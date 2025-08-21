from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.task.models import Task
from app.task.models import TaskStatus
from app.user.models import User as DBUser


async def test_create_task(
    async_client: AsyncClient,
    auth_token: str,
) -> None:
    payload = {
        "title": "Test Task",
        "description": "Task description",
        "status": "created",
    }
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await async_client.post("/tasks/", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["status"] == payload["status"]
    assert "id" in data


async def test_get_task(
    async_client: AsyncClient, auth_token: str, db_session: AsyncSession
) -> None:
    # create task directly in DB
    orm_stmt = select(DBUser)
    user_result = await db_session.execute(orm_stmt)
    user_object = user_result.scalar_one()
    task = Task(
        title="Get Task",
        description="Desc",
        status=TaskStatus.CREATED,
        owner_id=user_object.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await async_client.get(f"/tasks/{task.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == task.id
    assert data["title"] == task.title


async def test_update_task(
    async_client: AsyncClient,
    auth_token: str,
    db_session: AsyncSession,
) -> None:
    # create task
    orm_stmt = select(DBUser)
    user_result = await db_session.execute(orm_stmt)
    user_object = user_result.scalar_one()
    task = Task(
        title="Old Title",
        description="Old Desc",
        status=TaskStatus.CREATED,
        owner_id=user_object.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # update task
    payload = {"title": "New Title", "description": "New Desc", "status": "in_progress"}
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await async_client.put(f"/tasks/{task.id}", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Title"
    assert data["description"] == "New Desc"
    assert data["status"] == "in_progress"


async def test_delete_task_by_owner(
    async_client: AsyncClient,
    auth_token: str,
    db_session: AsyncSession,
) -> None:
    # create task
    orm_stmt = select(DBUser)
    user_result = await db_session.execute(orm_stmt)
    user_object = user_result.scalar_one()
    task = Task(
        title="Delete Me",
        description="Desc",
        status=TaskStatus.CREATED,
        owner_id=user_object.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await async_client.delete(f"/tasks/{task.id}", headers=headers)
    assert resp.status_code == 204


async def test_delete_task_by_admin(
    async_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    # create a task for a regular user
    orm_stmt = select(DBUser)
    user_result = await db_session.execute(orm_stmt)
    user_object = user_result.scalar_one()
    task = Task(
        title="Admin Delete",
        description="Desc",
        status=TaskStatus.CREATED,
        owner_id=user_object.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await async_client.delete(f"/tasks/{task.id}", headers=headers)
    assert resp.status_code == 204


async def test_get_tasks_list(
    async_client: AsyncClient,
    auth_token: str,
    db_session: AsyncSession,
) -> None:
    # create multiple task
    orm_stmt = select(DBUser)
    user_result = await db_session.execute(orm_stmt)
    user_object = user_result.scalar_one()
    for i in range(3):
        task = Task(
            title=f"Task {i}",
            description=f"Desc {i}",
            status=TaskStatus.CREATED,
            owner_id=user_object.id,
        )
        db_session.add(task)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await async_client.get("/tasks/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3


async def test_get_task_not_found(
    async_client: AsyncClient,
    user_a_token: str,
) -> None:
    """Tests that getting a non-existent task returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    headers = {"Authorization": f"Bearer {user_a_token}"}
    resp = await async_client.get(f"/tasks/{non_existent_id}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


async def test_update_task_not_found(
    async_client: AsyncClient,
    user_a_token: str,
) -> None:
    """Tests that updating a non-existent task returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    payload = {"title": "New Title"}
    headers = {"Authorization": f"Bearer {user_a_token}"}
    resp = await async_client.put(
        f"/tasks/{non_existent_id}",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


async def test_delete_task_not_found(
    async_client: AsyncClient,
    user_a_token: str,
) -> None:
    """Tests that deleting a non-existent task returns 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    headers = {"Authorization": f"Bearer {user_a_token}"}
    resp = await async_client.delete(
        f"/tasks/{non_existent_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task not found"


# --- 403 Forbidden / Authorization Tests ---


async def test_get_task_by_wrong_user(
    async_client: AsyncClient,
    user_a_task: Task,
    user_b_token: str,
) -> None:
    """Tests that User B cannot get User A's task."""
    headers = {"Authorization": f"Bearer {user_b_token}"}
    resp = await async_client.get(f"/tasks/{user_a_task.id}", headers=headers)
    # NOTE: This returns 404 because the query filters by owner_id, so from User B's
    # perspective, the task simply doesn't exist. This is correct and secure.
    assert resp.status_code == 404


async def test_update_task_by_wrong_user(
    async_client: AsyncClient,
    user_a_task: Task,
    user_b_token: str,
) -> None:
    """Tests that User B cannot update User A's task."""
    payload = {"title": "Attempted Hack"}
    headers = {"Authorization": f"Bearer {user_b_token}"}
    resp = await async_client.put(
        f"/tasks/{user_a_task.id}",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 404


async def test_delete_task_by_wrong_user(
    async_client: AsyncClient,
    user_a_task: Task,
    user_b_token: str,
) -> None:
    """Tests that User B (non-admin) cannot delete User A's task."""
    headers = {"Authorization": f"Bearer {user_b_token}"}
    resp = await async_client.delete(f"/tasks/{user_a_task.id}", headers=headers)
    # The delete endpoint has explicit owner/admin logic, so it returns a 403.
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Not enough permissions"
