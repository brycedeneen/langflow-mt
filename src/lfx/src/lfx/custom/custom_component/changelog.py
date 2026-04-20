"""Changelog primitives surfaced by the Update components modal."""

from pydantic import BaseModel, ConfigDict


class ChangelogEntry(BaseModel):
    """A single changelog entry tied to a component `version` bump.

    Authors append one of these per version bump. `changes` and `notes`
    both accept markdown and are rendered in the Update components modal.
    """

    model_config = ConfigDict(strict=True)

    version: int
    changes: str
    notes: str | None = None


import logging

logger = logging.getLogger(__name__)


def validate_changelog(cls: type) -> None:
    """Emit non-fatal warnings for malformed component version / changelog setups.

    Called from `Component.__init_subclass__`. Never raises — bad changelog data
    is an author mistake, not a reason to refuse to load the component.
    """
    entries = getattr(cls, "changelog", None) or []
    if not entries:
        return

    class_version = getattr(cls, "version", 0) or 0
    seen: set[int] = set()

    for entry in entries:
        if entry.version < 1:
            logger.warning(
                "%s.changelog entry version must be >= 1, got %s.",
                cls.__name__,
                entry.version,
            )
        if entry.version in seen:
            logger.warning(
                "%s.changelog has duplicate version %s.",
                cls.__name__,
                entry.version,
            )
        seen.add(entry.version)
        if entry.version > class_version:
            logger.warning(
                "%s.changelog entry version %s exceeds class version %s.",
                cls.__name__,
                entry.version,
                class_version,
            )
