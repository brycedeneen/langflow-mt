from typer.testing import CliRunner

from langflow.__main__ import app


def test_worker_help_lists_subcommand():
    result = CliRunner().invoke(app, ["worker", "--help"])
    assert result.exit_code == 0, result.output
    assert "queue" in result.output.lower()
