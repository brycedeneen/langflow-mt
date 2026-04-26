from typer.testing import CliRunner

from langflow.__main__ import app


def test_worker_help_lists_subcommand():
    result = CliRunner().invoke(app, ["worker", "--help"])
    assert result.exit_code == 0, result.output
    assert "queue" in result.output.lower()


def test_worker_passes_task_modules_to_taskiq(monkeypatch):
    """Each child process must re-import task modules so @broker.task decorators fire."""
    captured: dict[str, list[str]] = {}

    class FakeWorkerCMD:
        def exec(self, args):
            captured["args"] = args
            return 0

    import taskiq.cli.worker.cmd as cmd_mod
    monkeypatch.setattr(cmd_mod, "WorkerCMD", FakeWorkerCMD)

    result = CliRunner().invoke(app, ["worker", "-q", "runs:default", "--concurrency", "4"])
    assert result.exit_code == 0, result.output

    args = captured["args"]
    assert args[0] == "langflow.worker_app.brokers:broker_default"
    expected_modules = {
        "langflow.worker_app.settings",
        "langflow.worker_app.execute",
        "langflow.worker_app.webhook",
        "langflow.worker_app.reaper",
        "langflow.worker_app.retention",
        "langflow.worker_app.audit_cleanup",
        "langflow.worker_app.pricing_refresh",
        "langflow.worker_app.queue_depth",
    }
    positionals: list[str] = []
    i = 1
    while i < len(args) and not args[i].startswith("--"):
        positionals.append(args[i])
        i += 1
    assert set(positionals) == expected_modules, positionals
    assert "--workers" in args and "4" in args
