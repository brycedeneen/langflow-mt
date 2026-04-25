"""Regression test for lazy-loading of heavy langchain_classic imports.

If this test starts failing, someone has added an eager `import langchain_classic.*`
somewhere in lfx.field_typing's import graph. Move it behind TYPE_CHECKING or a
lazy helper.
"""
import subprocess
import sys
import textwrap


def test_field_typing_constants_does_not_eagerly_load_langchain_classic():
    """Importing lfx.field_typing.constants must not pull in langchain_classic.*."""
    script = textwrap.dedent(
        """
        import sys
        import lfx.field_typing.constants  # noqa: F401

        leaked = sorted(
            name for name in sys.modules
            if name == "langchain_classic" or name.startswith("langchain_classic.")
        )
        if leaked:
            print("LEAKED:" + ",".join(leaked))
            sys.exit(1)
        print("CLEAN")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"langchain_classic eagerly loaded by lfx.field_typing.constants:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
