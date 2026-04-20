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
