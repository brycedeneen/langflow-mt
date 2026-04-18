"""Tests for webhook API key generation and validation."""

import hmac
import re

import pytest


class TestWebhookApiKeyGeneration:
    def test_generate_webhook_api_key_format(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        key = generate_webhook_api_key()
        assert key.startswith("ADP-APICPRO-")
        suffix = key[len("ADP-APICPRO-"):]
        assert len(suffix) == 48

    def test_generate_webhook_api_key_uniqueness(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        keys = {generate_webhook_api_key() for _ in range(100)}
        assert len(keys) == 100  # all unique

    def test_generate_webhook_api_key_url_safe(self):
        from langflow.services.database.models.flow.utils import generate_webhook_api_key

        key = generate_webhook_api_key()
        suffix = key[len("ADP-APICPRO-"):]
        # URL-safe base64 uses only alphanumeric, hyphen, and underscore
        assert re.match(r'^[A-Za-z0-9_-]+$', suffix)

    def test_constant_time_compare_valid(self):
        key = "ADP-APICPRO-abc123"
        assert hmac.compare_digest(key, key) is True

    def test_constant_time_compare_invalid(self):
        assert hmac.compare_digest("ADP-APICPRO-abc123", "ADP-APICPRO-wrong") is False


from unittest.mock import AsyncMock, patch


class TestWebhookKeyProvisioning:
    @pytest.mark.asyncio
    async def test_provision_webhook_key_stores_in_vault(self):
        """When a flow has a webhook component and no key exists, one is generated and stored."""
        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value=None)  # no existing key
        mock_store.put = AsyncMock()

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=True,
            )

        assert key is not None
        assert key.startswith("ADP-APICPRO-")
        mock_store.put.assert_called_once()
        call_args = mock_store.put.call_args
        assert call_args[0][0] == "org-123/webhooks/flow-456"
        assert "api_key" in call_args[0][1]
        assert "created_at" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_provision_skips_when_key_exists(self):
        """When a key already exists, don't regenerate."""
        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value={"api_key": "ADP-APICPRO-existing", "created_at": "2026-01-01"})

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=True,
            )

        assert key == "ADP-APICPRO-existing"
        mock_store.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_provision_returns_none_when_no_webhook(self):
        """When flow has no webhook component, return None and don't touch the store."""
        mock_store = AsyncMock()

        with patch("langflow.api.v1.flows.get_secret_store", return_value=mock_store):
            from langflow.api.v1.flows import _provision_webhook_api_key

            key = await _provision_webhook_api_key(
                org_id="org-123",
                flow_id="flow-456",
                has_webhook=False,
            )

        assert key is None
        mock_store.get.assert_not_called()
        mock_store.put.assert_not_called()
