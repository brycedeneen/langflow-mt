"""Tests for SecretStrInput's auto_promote default behavior."""

from lfx.inputs.inputs import SecretStrInput, TextFileSecretInput


def test_secret_str_input_auto_promote_default_is_true():
    inp = SecretStrInput(name="api_key")
    assert inp.auto_promote is True


def test_auto_promote_can_be_explicitly_disabled():
    inp = SecretStrInput(name="api_key", auto_promote=False)
    assert inp.auto_promote is False


def test_text_file_secret_input_inherits_auto_promote_default():
    inp = TextFileSecretInput(name="cert_pem", file_types=["pem"])
    assert inp.auto_promote is True


def test_auto_promote_is_serialized_in_model_dump():
    inp = SecretStrInput(name="api_key")
    dumped = inp.model_dump()
    assert dumped["auto_promote"] is True


def test_auto_promote_false_is_serialized():
    inp = SecretStrInput(name="api_key", auto_promote=False)
    dumped = inp.model_dump()
    assert dumped["auto_promote"] is False
