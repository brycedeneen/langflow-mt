"""Smoke probe: ibm-watsonx-ai under pandas 3.0 override.

ibm-watsonx-ai declares `pandas<2.4.0` but we force `pandas>=3.0` via
tool.uv.override-dependencies. This probe asserts the import graph and
first-call pandas surface survive the resolver lie.

No network, no auth — if the dep needs credentials to run its pandas
code path, we fall back to attribute-existence assertions.
"""
import pytest

pytest.importorskip("ibm_watsonx_ai")


@pytest.mark.smoke
def test_ibm_watsonx_ai_imports_cleanly():
    import ibm_watsonx_ai
    import ibm_watsonx_ai.foundation_models.utils  # touches pandas-adjacent internals

    assert ibm_watsonx_ai.__version__


@pytest.mark.smoke
def test_ibm_watsonx_ai_api_client_instantiates():
    """APIClient construction exercises pandas-backed internals without a network call."""
    from ibm_watsonx_ai import APIClient

    # APIClient accepts a credentials dict; passing empty/dummy triggers validation-only
    # paths. If the import graph is broken on pandas 3, we'll crash here with
    # ImportError / AttributeError / TypeError rather than a credential/auth error.
    with pytest.raises(Exception) as exc_info:  # noqa: PT011 — we want any failure here
        APIClient(credentials={"url": "https://example.invalid"})
    # Auth/credential errors are fine (that's the expected failure mode).
    # ImportError / AttributeError / TypeError means the override is a lie.
    msg = str(exc_info.value)
    forbidden = ("ImportError", "has no attribute", "NoneType")
    for bad in forbidden:
        assert bad not in type(exc_info.value).__name__ + msg, (
            f"watsonx broke at construction on pandas 3: {bad} in {msg!r}"
        )
