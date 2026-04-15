from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel


def test_log_level_enum():
    assert {l.value for l in LogLevel} == {"debug", "info", "warn", "error"}


def test_flow_run_log_fields():
    required = {"id", "run_id", "ts", "level", "node_id", "message", "extra"}
    assert required.issubset(FlowRunLog.model_fields)
