from langflow.worker_app.settings import WorkerSettings


def test_worker_settings_registers_tasks():
    names = {f.__name__ if not isinstance(f, str) else f for f in WorkerSettings.functions}
    assert "execute_run" in names
    assert "deliver_webhook" in names
    assert any(cron.name == "reap_lost_runs" for cron in WorkerSettings.cron_jobs)
    assert any(cron.name == "retention_sweep" for cron in WorkerSettings.cron_jobs)
