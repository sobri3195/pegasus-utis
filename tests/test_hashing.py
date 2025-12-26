from utis.core.hashing import compute_event_hash


def test_compute_event_hash_stable():
    h1 = compute_event_hash(
        "1",
        "entity",
        "type",
        {"a": 1},
        "2024-01-01T00:00:00+00:00",
        "source",
        None,
    )
    h2 = compute_event_hash(
        "1",
        "entity",
        "type",
        {"a": 1},
        "2024-01-01T00:00:00+00:00",
        "source",
        None,
    )
    assert h1 == h2
