from __future__ import annotations
import importlib


def test_worker_tunables_have_defaults():
    from lfx.services.settings.base import Settings
    s = Settings(_env_file=None)
    assert s.worker_heartbeat_interval_s == 15.0
    assert s.worker_cancel_poll_interval_s == 2.0
    assert s.worker_requeue_delay_s == 5.0
    assert s.worker_log_flush_interval_s == 0.5
    assert s.worker_log_max_buffer == 100
    assert s.worker_max_run_timeout_seconds == 3600
    assert s.worker_retry_jitter_ratio == 0.1
    assert s.worker_webhook_backoff_schedule_s == [10, 30, 120, 600, 1800, 3600]
    assert s.worker_shutdown_drain_timeout_s == 30.0


def test_worker_tunables_read_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WORKER_HEARTBEAT_INTERVAL_S", "7.5")
    monkeypatch.setenv("LANGFLOW_WORKER_REQUEUE_DELAY_S", "2")
    monkeypatch.setenv("LANGFLOW_WORKER_MAX_RUN_TIMEOUT_SECONDS", "1800")
    from lfx.services.settings import base as base_mod
    importlib.reload(base_mod)
    s = base_mod.Settings(_env_file=None)
    assert s.worker_heartbeat_interval_s == 7.5
    assert s.worker_requeue_delay_s == 2.0
    assert s.worker_max_run_timeout_seconds == 1800
