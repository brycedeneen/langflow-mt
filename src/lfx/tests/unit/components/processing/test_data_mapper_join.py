from lfx.components.processing._data_mapper.config_schema import JoinDef, JoinKey
from lfx.components.processing._data_mapper.join import build_index, lookup


def _join(*pairs):
    return JoinDef(on=[JoinKey(driver_field=d, lookup_field=l) for d, l in pairs])


def test_single_key_index_and_lookup():
    jobs = [
        {"id": "j-1", "title": "Engineer"},
        {"id": "j-2", "title": "Manager"},
    ]
    join = _join(("job_id", "id"))
    index, collisions = build_index(jobs, join)

    driver_row = {"job_id": "j-1"}
    assert lookup(index, driver_row, join) == {"id": "j-1", "title": "Engineer"}
    assert collisions == 0


def test_composite_key_and_match():
    jobs = [
        {"id": "j-1", "org_id": "o-1", "title": "Eng NYC"},
        {"id": "j-1", "org_id": "o-2", "title": "Eng SF"},
    ]
    join = _join(("job_id", "id"), ("org_id", "org_id"))
    index, _ = build_index(jobs, join)

    driver_row = {"job_id": "j-1", "org_id": "o-2"}
    assert lookup(index, driver_row, join)["title"] == "Eng SF"


def test_unmatched_lookup_returns_none():
    jobs = [{"id": "j-1", "title": "Engineer"}]
    join = _join(("job_id", "id"))
    index, _ = build_index(jobs, join)

    driver_row = {"job_id": "j-99"}
    assert lookup(index, driver_row, join) is None


def test_first_match_wins_on_duplicate_keys():
    jobs = [
        {"id": "j-1", "title": "First"},
        {"id": "j-1", "title": "Second"},
        {"id": "j-1", "title": "Third"},
    ]
    join = _join(("job_id", "id"))
    index, collisions = build_index(jobs, join)

    driver_row = {"job_id": "j-1"}
    assert lookup(index, driver_row, join)["title"] == "First"
    assert collisions == 2  # 2 duplicates shadowed


def test_missing_driver_key_returns_none():
    jobs = [{"id": "j-1"}]
    join = _join(("job_id", "id"))
    index, _ = build_index(jobs, join)

    driver_row = {}  # no job_id at all
    assert lookup(index, driver_row, join) is None


def test_missing_lookup_key_is_treated_as_none_key():
    jobs = [{"other_field": "x"}]  # no 'id' field
    join = _join(("job_id", "id"))
    index, _ = build_index(jobs, join)

    driver_row = {"job_id": None}
    # Row with None key is still indexed; driver with None key matches.
    assert lookup(index, driver_row, join) == {"other_field": "x"}
