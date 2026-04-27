from __future__ import annotations

from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.field_typing import ErrorPayload  # noqa: F401  (registered for type validator)
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import (
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    MultilineInput,
    Output,
    StrInput,
)


_DEFAULT_TITLE_TEMPLATE = "Flow '{flow_name}' failed at {component_name}"
_DEFAULT_BODY_TEMPLATE = (
    "**Error:** {error_message}\n\n"
    "**Component:** {component_name}\n"
    "**Type:** {error_type}\n"
    "**Attempt:** {attempt_number}\n\n"
    "```\n{stack_trace}\n```"
)


class ErrorHandler(Component):
    """Catches errors emitted by upstream components' error ports.

    Configures retry attempts + backoff, dispatches a single alert per
    handled error, and emits `gave_up` with the original ErrorPayload after
    retries are exhausted.

    Does NOT itself expose an `error` output — exceptions raised inside
    ErrorHandler bypass the runtime extension and fail the flow run.
    """

    display_name = "Error Handler"
    description = (
        "Retry a failing component with backoff and dispatch an alert when "
        "retries are exhausted."
    )
    icon = "shield-alert"
    name = "ErrorHandler"
    error_output_enabled: ClassVar[bool] = False  # explicit: no nested recovery

    inputs = [
        HandleInput(
            name="error_input",
            display_name="Error",
            input_types=["ErrorPayload"],
            info="Connect a component's Error output here.",
        ),
        IntInput(
            name="max_attempts",
            display_name="Max retry attempts",
            value=3,
            range_spec=RangeSpec(min=0, max=10),
            info="0 = no retry, fire alert immediately. Max 10.",
        ),
        DropdownInput(
            name="alert_mode",
            display_name="Alert mode",
            options=["Bell", "Email (Not Implemented)", "Ignore"],
            value="Bell",
        ),
        DropdownInput(
            name="bell_audience",
            display_name="Bell audience",
            options=["Flow owner", "Org admins", "Specific user"],
            value="Flow owner",
            show=True,
        ),
        StrInput(
            name="bell_specific_user_id",
            display_name="Specific user",
            info="User ID (UUID format) to notify when bell audience = Specific user.",
            advanced=True,
        ),
        StrInput(
            name="alert_title_template",
            display_name="Alert title",
            value=_DEFAULT_TITLE_TEMPLATE,
            info="Available variables: {flow_name}, {component_name}, {error_type}, {error_message}, {attempt_number}, {org_name}",
        ),
        DropdownInput(
            name="backoff_strategy",
            display_name="Backoff strategy",
            options=["None", "Fixed delay", "Exponential", "Exponential with jitter"],
            value="Exponential with jitter",
            advanced=True,
        ),
        FloatInput(
            name="base_delay_seconds",
            display_name="Base delay (s)",
            value=1.0,
            advanced=True,
        ),
        FloatInput(
            name="max_delay_seconds",
            display_name="Max delay (s)",
            value=60.0,
            advanced=True,
        ),
        MultilineInput(
            name="alert_body_template",
            display_name="Alert body (markdown)",
            value=_DEFAULT_BODY_TEMPLATE,
            advanced=True,
            info="Markdown. Available variables: {flow_name}, {component_name}, {error_type}, {error_message}, {attempt_number}, {stack_trace}, {org_name}",
        ),
    ]

    outputs = [
        Output(
            display_name="Gave up",
            name="gave_up",
            types=["ErrorPayload"],
            method="on_error_exhausted",
        ),
    ]

    async def on_error_exhausted(self) -> ErrorPayload:
        """Fired by the runtime after retries exhaust + alert dispatched.

        The runtime constructs and passes the ErrorPayload directly via the
        runtime extension; this method is the public output endpoint.
        """
        msg = "ErrorHandler.on_error_exhausted is wired by the runtime; do not invoke directly"
        raise NotImplementedError(msg)
