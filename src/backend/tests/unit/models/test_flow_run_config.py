from langflow.services.database.models.flow.model import Flow


def test_flow_run_config_fields():
    fields = Flow.model_fields
    for name in ("webhook_url", "webhook_secret", "auto_retry", "max_retries", "timeout_seconds"):
        assert name in fields, f"missing {name}"
