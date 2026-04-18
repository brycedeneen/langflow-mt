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
