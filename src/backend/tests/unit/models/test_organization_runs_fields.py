from langflow.services.database.models.organization.model import Organization


def test_organization_runs_fields_exist():
    fields = Organization.model_fields
    assert "runs_max_concurrent" in fields
    assert "runs_priority_tier" in fields
