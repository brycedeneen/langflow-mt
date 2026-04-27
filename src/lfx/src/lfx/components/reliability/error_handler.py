from __future__ import annotations

import logging
import warnings
from typing import ClassVar
from uuid import UUID

from langflow.services.database.models.admin_notification import NotificationAudience
from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier

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

logger = logging.getLogger(__name__)


def _resolve_audience(
    bell_audience: str,
    flow_owner_id: UUID,
    specific_user_id: UUID | None,
) -> tuple[NotificationAudience, UUID | None]:
    if bell_audience == "Flow owner":
        return NotificationAudience.PLATFORM_ADMIN, flow_owner_id
    if bell_audience == "Org admins":
        return NotificationAudience.PLATFORM_ADMIN, None
    if bell_audience == "Specific user":
        return NotificationAudience.PLATFORM_ADMIN, specific_user_id
    msg = f"Unknown bell_audience: {bell_audience!r}"
    raise ValueError(msg)


def _render_template(
    template: str,
    payload: ErrorPayload,
    *,
    flow_name: str,
    org_name: str,
) -> str:
    try:
        return template.format(
            flow_name=flow_name,
            org_name=org_name,
            component_name=payload.component_display_name,
            error_type=payload.error_type,
            error_message=payload.error_message,
            attempt_number=payload.attempt_number,
            stack_trace=payload.stack_trace,
        )
    except KeyError as exc:
        # User template references an unknown variable. Don't drop the alert —
        # surface the misconfiguration in the body and keep the error message visible.
        logger.warning("ErrorHandler template references unknown variable %s", exc)
        return f"[Template error: unknown variable {exc}] {payload.error_message}"


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

    async def dispatch_alert(
        self,
        *,
        payload: ErrorPayload,
        notifier: UsageAlertNotifier,
        flow_owner_id: UUID,
        org_id: UUID,
        flow_name: str,
        org_name: str,
    ) -> None:
        """Dispatch the configured alert. Best-effort — exceptions are logged and swallowed."""
        if self.alert_mode == "Ignore":
            return

        # Email (Not Implemented) falls through to Bell in v1.
        if self.alert_mode == "Email (Not Implemented)":
            warnings.warn(
                "ErrorHandler email mode is not implemented; falling through to Bell.",
                UserWarning,
                stacklevel=2,
            )

        specific_id: UUID | None = None
        if self.bell_audience == "Specific user":
            if not self.bell_specific_user_id:
                logger.warning(
                    "ErrorHandler bell_audience='Specific user' but no user_id provided; alert suppressed."
                )
                return
            try:
                specific_id = UUID(self.bell_specific_user_id)
            except (ValueError, AttributeError):
                logger.warning(
                    "ErrorHandler bell_specific_user_id %r is not a valid UUID; alert suppressed.",
                    self.bell_specific_user_id,
                )
                return

        try:
            audience, audience_user_id = _resolve_audience(
                self.bell_audience, flow_owner_id, specific_id
            )
            title = _render_template(
                self.alert_title_template, payload,
                flow_name=flow_name, org_name=org_name,
            )
            body = _render_template(
                self.alert_body_template, payload,
                flow_name=flow_name, org_name=org_name,
            )
            event = UsageAlertEvent(
                category="flow_error",
                severity="error",
                org_id=org_id,
                title=title,
                body_md=body,
                metadata={
                    "vertex_id": payload.component_id,
                    "attempt_number": payload.attempt_number,
                    "error_type": payload.error_type,
                },
                audience=audience,
                audience_user_id=audience_user_id,
            )
            await notifier.notify(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ErrorHandler alert dispatch failed: %s", exc)
