"""Security tests for monitor endpoints requiring authentication."""

import pytest
from fastapi import status
from httpx import AsyncClient


async def test_get_messages_requires_auth(shared_client: AsyncClient):
    """Test that GET /monitor/messages requires authentication."""
    response = await shared_client.get("api/v1/monitor/messages")
    # Langflow returns 403 for missing/invalid authentication
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_transactions_requires_auth(shared_client: AsyncClient):
    """Test that GET /monitor/transactions requires authentication."""
    # Include required query parameter
    response = await shared_client.get("api/v1/monitor/transactions?flow_id=00000000-0000-0000-0000-000000000000")
    # Langflow returns 403 for missing/invalid authentication
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_delete_messages_session_requires_auth(shared_client: AsyncClient):
    """Test that DELETE /monitor/messages/session/{session_id} requires authentication."""
    response = await shared_client.delete("api/v1/monitor/messages/session/test-session")
    # Langflow returns 403 for missing/invalid authentication
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_messages_with_fake_token(shared_client: AsyncClient):
    """Test that GET /monitor/messages rejects fake tokens."""
    response = await shared_client.get("api/v1/monitor/messages", headers={"Authorization": "Bearer fake-token"})
    # Langflow returns 401 for invalid Bearer tokens (JWT validation fails)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_get_transactions_with_fake_token(shared_client: AsyncClient):
    """Test that GET /monitor/transactions rejects fake tokens."""
    response = await shared_client.get(
        "api/v1/monitor/transactions?flow_id=00000000-0000-0000-0000-000000000000",
        headers={"Authorization": "Bearer fake-token"},
    )
    # Langflow returns 401 for invalid Bearer tokens (JWT validation fails)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_delete_messages_session_with_fake_token(shared_client: AsyncClient):
    """Test that DELETE /monitor/messages/session/{session_id} rejects fake tokens."""
    response = await shared_client.delete(
        "api/v1/monitor/messages/session/test-session", headers={"Authorization": "Bearer fake-token"}
    )
    # Langflow returns 401 for invalid Bearer tokens (JWT validation fails)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---- Tests below use logged_in_headers (transitive client dependency) ----
# These 3 tests remain on the function-scoped `client` fixture until
# shared_logged_in_headers is implemented (see migration followups doc).


@pytest.mark.usefixtures("active_user")
async def test_get_messages_with_valid_auth(client: AsyncClient, logged_in_headers):
    """Test that GET /monitor/messages works with valid authentication."""
    response = await client.get("api/v1/monitor/messages", headers=logged_in_headers)
    # Should return 200 OK (even if empty list)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


@pytest.mark.usefixtures("active_user")
async def test_get_transactions_with_valid_auth(client: AsyncClient, logged_in_headers):
    """Valid auth + a nonexistent flow_id → 404 (org-scoped lookup)."""
    response = await client.get(
        "api/v1/monitor/transactions?flow_id=00000000-0000-0000-0000-000000000000", headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("active_user")
async def test_delete_messages_session_with_valid_auth(client: AsyncClient, logged_in_headers):
    """Test that DELETE /monitor/messages/session/{session_id} works with valid authentication."""
    response = await client.delete("api/v1/monitor/messages/session/test-session", headers=logged_in_headers)
    # Should return 204 No Content
    assert response.status_code == status.HTTP_204_NO_CONTENT
