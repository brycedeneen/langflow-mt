from langflow.services.runs.webhook_sign import sign_body, verify_body


def test_sign_and_verify_roundtrip():
    body = b'{"event":"run.started"}'
    secret = "s3cret"
    sig = sign_body(body, secret)
    assert sig.startswith("sha256=")
    assert verify_body(body, secret, sig)
    assert not verify_body(body, secret, "sha256=deadbeef")
