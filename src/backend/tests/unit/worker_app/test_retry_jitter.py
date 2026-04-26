from __future__ import annotations
import random
from langflow.worker_app.execute import _jittered_backoff


def test_jittered_backoff_zero_ratio_is_deterministic():
    assert _jittered_backoff(60.0, 0.0) == 60.0


def test_jittered_backoff_within_band():
    rng = random.Random(0)
    for _ in range(100):
        v = _jittered_backoff(60.0, 0.1, rng=rng)
        assert 60.0 <= v <= 66.0


def test_jittered_backoff_does_not_cap():
    """Caller is responsible for capping; helper just adds jitter."""
    v = _jittered_backoff(10_000.0, 0.1, rng=random.Random(0))
    assert v >= 10_000.0
