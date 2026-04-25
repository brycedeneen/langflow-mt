from lfx.services.settings.base import Settings


def test_runs_settings_defaults(monkeypatch):
    # pydantic-settings reads LANGFLOW_* env vars even when _env_file=None.
    # The local dev .env (loaded in conftest) sets DISTRIBUTED_EXECUTION=true,
    # so unset the relevant vars to actually exercise the documented defaults.
    for var in (
        "LANGFLOW_DISTRIBUTED_EXECUTION",
        "LANGFLOW_REDIS_URL",
        "LANGFLOW_REDIS_HOST",
        "LANGFLOW_REDIS_PORT",
        "LANGFLOW_REDIS_DB",
    ):
        monkeypatch.delenv(var, raising=False)

    s = Settings(_env_file=None)
    assert s.distributed_execution is False
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.queue_default == "runs:default"
    assert s.queue_high == "runs:high"
    assert s.queue_low == "runs:low"
    assert s.queue_webhooks == "webhooks"
    assert s.worker_concurrency == 8
    assert s.run_retention_hours == 24
    assert s.run_payload_inline_max_bytes == 1 * 1024 * 1024
    assert s.run_logs_max_bytes == 10 * 1024 * 1024
    assert s.run_default_timeout_seconds == 600
    assert s.org_default_max_concurrent_runs == 5
