from unittest.mock import AsyncMock

import pytest

from langflow.services.professional_services.llm_service import (
    GeneratedQuoteText,
    generate_quote_text,
)


@pytest.mark.asyncio
async def test_generate_quote_text_returns_three_fields():
    fake_provider = AsyncMock()
    fake_provider.complete_structured.return_value = {
        "headline_summary": "Wire up Slack notifications.",
        "narrative": "User wants to forward build events to Slack.",
        "conversation_summary": "User struggled with OAuth setup.",
    }
    result = await generate_quote_text(
        flow_name="Slack notifier",
        component_breakdown=[{"type": "Webhook", "minutes_low": 15, "minutes_high": 60}],
        chat_history=[{"role": "user", "content": "I'm stuck on OAuth"}],
        provider=fake_provider,
    )
    assert isinstance(result, GeneratedQuoteText)
    assert result.headline_summary == "Wire up Slack notifications."
    assert result.narrative.startswith("User wants")
    assert result.conversation_summary is not None


@pytest.mark.asyncio
async def test_generate_quote_text_null_summary_when_no_chat():
    fake_provider = AsyncMock()
    fake_provider.complete_structured.return_value = {
        "headline_summary": "Forward webhook events.",
        "narrative": "Simple webhook forwarder.",
        "conversation_summary": None,
    }
    result = await generate_quote_text(
        flow_name="Forwarder",
        component_breakdown=[{"type": "Webhook", "minutes_low": 15, "minutes_high": 60}],
        chat_history=None,
        provider=fake_provider,
    )
    assert result.conversation_summary is None


@pytest.mark.asyncio
async def test_system_prompt_includes_secret_redaction_clause():
    """Verifies the system prompt forbids credentials/tokens in output."""
    from langflow.services.professional_services.llm_service import SYSTEM_PROMPT

    text = SYSTEM_PROMPT.lower()
    assert "api key" in text or "credential" in text
    assert "token" in text
    assert "never include" in text or "must not" in text or "do not include" in text
