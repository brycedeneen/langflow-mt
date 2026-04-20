"""Tests for TextFileSecretInput — a SecretStr-backed input that the frontend
renders with a Paste / Upload File tab toggle (file read client-side)."""

from lfx.inputs.inputs import SecretStrInput, TextFileSecretInput


def test_extends_secret_str_input():
    assert issubclass(TextFileSecretInput, SecretStrInput)


def test_input_type_discriminator_is_serialized():
    inp = TextFileSecretInput(name="cert_pem", file_types=["pem", "crt"])
    dumped = inp.model_dump()
    assert dumped["_input_type"] == "TextFileSecretInput"
    assert dumped["file_types"] == ["pem", "crt"]


def test_inherits_secret_str_password_and_load_from_db_defaults():
    inp = TextFileSecretInput(name="cert_pem", file_types=["pem"])
    assert inp.password is True
    assert inp.load_from_db is True


def test_file_types_defaults_to_empty_list():
    inp = TextFileSecretInput(name="cert_pem")
    assert inp.file_types == []


def test_file_types_accepts_extensions_without_dots():
    # Frontend file picker accept filter expects bare extensions or extensions
    # with leading dots; we mandate bare extensions for consistency.
    inp = TextFileSecretInput(name="x", file_types=["pem", "crt", "key"])
    assert inp.file_types == ["pem", "crt", "key"]
