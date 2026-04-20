"""Smoke probe: cleanlab-tlm under pandas 3.0 override.

cleanlab-tlm declares `pandas==2.*` but we force `pandas>=3.0`. This probe
verifies cleanlab-tlm imports cleanly and exposes its pandas-consuming
surface after the override.
"""
import importlib.metadata

import pytest

pytest.importorskip("cleanlab_tlm")


@pytest.mark.smoke
def test_cleanlab_tlm_imports_cleanly():
    import cleanlab_tlm  # noqa: F401
    from cleanlab_tlm import TLM

    assert TLM is not None
    # cleanlab_tlm does not expose __version__ as a module attribute;
    # use importlib.metadata so we still assert the dep is resolvable.
    assert importlib.metadata.version("cleanlab-tlm")


@pytest.mark.smoke
def test_cleanlab_tlm_tlm_class_is_usable():
    """TLM construction exercises cleanlab-tlm's pandas-touching internals.

    TLM does not require pandas 2-specific APIs at construction, only at data-handling
    calls we don't make here. If construction fails with ImportError / AttributeError,
    the override is a lie.
    """
    from cleanlab_tlm import TLM

    # TLM() typically requires an api_key; passing none or dummy should surface a
    # clean ValueError / auth error — not an ImportError or pandas AttributeError.
    try:
        TLM()
    except (ImportError, AttributeError) as e:
        pytest.fail(
            f"cleanlab-tlm broke on pandas 3 override: {type(e).__name__}: {e}"
        )
    except Exception:
        # Auth / config / value errors are fine — they're not the failure mode we care about.
        pass
