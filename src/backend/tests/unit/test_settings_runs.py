from lfx.services.settings.base import Settings


def test_runs_settings_defaults():
    s = Settings(_env_file=None)
    assert s.distributed_execution is False
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.arq_default_queue == "runs:default"
    assert s.arq_high_queue == "runs:high"
    assert s.arq_low_queue == "runs:low"
    assert s.arq_webhooks_queue == "webhooks"
    assert s.worker_concurrency == 8
    assert s.run_retention_hours == 24
    assert s.run_payload_inline_max_bytes == 1 * 1024 * 1024
    assert s.run_logs_max_bytes == 10 * 1024 * 1024
    assert s.run_default_timeout_seconds == 600
    assert s.org_default_max_concurrent_runs == 5
