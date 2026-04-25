"""ADPToolsComponent — single multi-select component exposing ADP tile groups as agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from lfx.components.adp._shared import ADPConnection, RequestCache
from lfx.components.adp.adp_applicant_onboarding_tools import build_applicant_onboarding_tools
from lfx.components.adp.adp_benefits_tools import build_benefits_tools
from lfx.components.adp.adp_data_collection_entries_tools import build_data_collection_entries_tools
from lfx.components.adp.adp_deduction_configurations_tools import build_deduction_configurations_tools
from lfx.components.adp.adp_job_applicants_tools import build_job_applicants_tools
from lfx.components.adp.adp_job_requisitions_tools import build_job_requisitions_tools
from lfx.components.adp.adp_pay_data_input_tools import build_pay_data_input_tools
from lfx.components.adp.adp_pay_distributions_tools import build_pay_distributions_tools
from lfx.components.adp.adp_pay_statements_tools import build_pay_statements_tools
from lfx.components.adp.adp_talent_tools import build_talent_tools
from lfx.components.adp.adp_team_time_cards_tools import build_team_time_cards_tools
from lfx.components.adp.adp_time_cards_tools import build_time_cards_tools
from lfx.components.adp.adp_time_off_tools import build_time_off_tools
from lfx.components.adp.adp_us_tax_profiles_tools import build_us_tax_profiles_tools
from lfx.components.adp.adp_work_schedules_tools import build_work_schedules_tools
from lfx.components.adp.adp_worker_assignment_tools import build_worker_assignment_tools
from lfx.components.adp.adp_worker_assignment_v3_tools import build_worker_assignment_v3_tools
from lfx.components.adp.adp_worker_biological_tools import build_worker_biological_tools
from lfx.components.adp.adp_worker_business_communication_tools import build_worker_business_communication_tools
from lfx.components.adp.adp_worker_compensation_tools import build_worker_compensation_tools
from lfx.components.adp.adp_worker_demographic_tools import build_worker_demographic_tools
from lfx.components.adp.adp_worker_deployment_tools import build_worker_deployment_tools
from lfx.components.adp.adp_worker_hr_profiles_tools import build_worker_hr_profiles_tools
from lfx.components.adp.adp_worker_identification_tools import build_worker_identification_tools
from lfx.components.adp.adp_worker_leaves_tools import build_worker_leaves_tools
from lfx.components.adp.adp_worker_lifecycle_tools import build_worker_lifecycle_tools
from lfx.components.adp.adp_worker_payroll_instructions_tools import build_worker_payroll_instructions_tools
from lfx.components.adp.adp_worker_personal_communication_tools import build_worker_personal_communication_tools
from lfx.components.adp.adp_worker_tools import build_worker_tools
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry
from lfx.io import HandleInput, MultiselectInput, Output

if TYPE_CHECKING:
    from collections.abc import Callable


TILE_BUILDERS: dict[str, Callable[[ADPConnection, RequestCache], list[Tool]]] = {
    "Worker": build_worker_tools,
    "Worker Assignment": build_worker_assignment_tools,
    "Worker Assignment v3": build_worker_assignment_v3_tools,
    "Worker HR Profiles": build_worker_hr_profiles_tools,
    "Worker Lifecycle": build_worker_lifecycle_tools,
    "Worker Identification": build_worker_identification_tools,
    "Worker Biological": build_worker_biological_tools,
    "Worker Deployment": build_worker_deployment_tools,
    "Worker Leaves": build_worker_leaves_tools,
    "Worker Payroll Instructions": build_worker_payroll_instructions_tools,
    "Worker Personal Communication": build_worker_personal_communication_tools,
    "Worker Business Communication": build_worker_business_communication_tools,
    "Worker Compensation": build_worker_compensation_tools,
    "Worker Demographic": build_worker_demographic_tools,
    "Pay Data Input": build_pay_data_input_tools,
    "Pay Distributions": build_pay_distributions_tools,
    "Pay Statements": build_pay_statements_tools,
    "US Tax Profiles": build_us_tax_profiles_tools,
    "Deduction Configurations": build_deduction_configurations_tools,
    "Time Cards": build_time_cards_tools,
    "Team Time Cards": build_team_time_cards_tools,
    "Time Off": build_time_off_tools,
    "Work Schedules": build_work_schedules_tools,
    "Talent": build_talent_tools,
    "Job Applicants": build_job_applicants_tools,
    "Job Requisitions": build_job_requisitions_tools,
    "Applicant Onboarding": build_applicant_onboarding_tools,
    "Benefits": build_benefits_tools,
    "Data Collection Entries": build_data_collection_entries_tools,
}


class ADPToolsComponent(Component):
    display_name = "ADP Tools"
    name = "ADPTools"
    description = (
        "Exposes ADP HR, payroll, time, and talent tools to a Langflow Agent. "
        "Pick which tile groups you want — each contributes 1-15 agent tools."
    )
    icon = "Users"
    version: int = 1
    documentation: str = "https://docs.langflow.org/component-adp-tools"

    inputs: ClassVar = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        MultiselectInput(
            name="tiles",
            display_name="Tools",
            options=list(TILE_BUILDERS.keys()),
            value=[],
            info=(
                "Select which ADP tool groups to expose to the agent. Each group "
                "adds 1-15 focused agent tools. Leaving this empty exposes nothing."
            ),
        ),
    ]

    outputs: ClassVar = [Output(display_name="Tools", name="tools", method="build_tools")]

    async def build_tools(self) -> list[Tool]:
        selected = list(getattr(self, "tiles", []) or [])
        if not selected:
            self.status = "No tile groups selected — agent will receive 0 ADP tools."
            return []
        cache = RequestCache(ttl_seconds=30, max_entries=128)
        tools: list[Tool] = []
        for label in selected:
            builder = TILE_BUILDERS.get(label)
            if builder is None:
                continue  # defensive: stale label from a saved flow
            tools.extend(builder(self.connection, cache))
        self.status = f"Exposing {len(tools)} tool(s) from {len(selected)} tile group(s)."
        return tools
