from http import HTTPStatus


async def test_auth_workflow(app_with_db, async_client, test_user):
    """
    Tests the full authentication flow:
    1. Logs in a test user.
    2. Verifies a successful login and token retrieval.
    """
    username, password = test_user

    login_response = await async_client.post(
        "users/token",
        data={"username": username, "password": password},
    )

    assert login_response.status_code == HTTPStatus.OK, (
        f"Login failed. Expected {HTTPStatus.OK}, got {login_response.status_code}. "
        f"Response: {login_response.text}"
    )

    response_json = login_response.json()
    assert (
        "access_token" in response_json
    ), "Access token not found in the login response."

    access_token = response_json.get("access_token")
    assert (
        isinstance(access_token, str) and access_token
    ), "Access token is not a valid string."
