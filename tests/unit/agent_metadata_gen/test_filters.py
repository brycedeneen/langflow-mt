"""Tests for the per-class filter rules used by the generator entry point."""
from __future__ import annotations

from typing import ClassVar

from scripts._agent_metadata_gen import generate as gen


class _OptedOut:
    assist_enabled: ClassVar[bool] = False
    legacy: ClassVar[bool] = False
    display_name = "Opted Out"
    description = "opted out"
    inputs = []
    outputs = []


class _Legacy:
    assist_enabled: ClassVar[bool] = True
    legacy: ClassVar[bool] = True
    display_name = "Legacy"
    description = "legacy"
    inputs = []
    outputs = []


class _Eligible:
    display_name = "Eligible"
    description = "eligible"
    inputs = []
    outputs = []


def test_decide_outcome_skips_opted_out():
    outcome = gen.decide_outcome(_OptedOut, existing_types=set(), overwrite=False)
    assert outcome == "skipped-opted-out"


def test_decide_outcome_skips_legacy():
    outcome = gen.decide_outcome(_Legacy, existing_types=set(), overwrite=False)
    assert outcome == "skipped-legacy"


def test_decide_outcome_skips_existing_when_no_overwrite():
    outcome = gen.decide_outcome(
        _Eligible, existing_types={"_Eligible"}, overwrite=False,
    )
    assert outcome == "skipped-existing"


def test_decide_outcome_overwrite_processes_existing():
    outcome = gen.decide_outcome(
        _Eligible, existing_types={"_Eligible"}, overwrite=True,
    )
    assert outcome == "processed"


def test_decide_outcome_processes_new_eligible():
    outcome = gen.decide_outcome(
        _Eligible, existing_types=set(), overwrite=False,
    )
    assert outcome == "processed"
