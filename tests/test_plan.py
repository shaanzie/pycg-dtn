from __future__ import annotations

from pycg_dtn import Contact, ContactPlan


def _contact(**kwargs) -> Contact:
    args = {
        "a": "A",
        "b": "B",
        "a_eid": "dtn:a",
        "b_eid": "dtn:b",
        "kind": "inter",
        "start_et": 100.0,
        "stop_et": 200.0,
        "rate_bps": 1000.0,
        "owlt_s": 1.5,
        "owlt_min_s": 1.4,
        "owlt_max_s": 1.6,
        "range_min_km": 1.0,
        "range_max_km": 2.0,
    }
    args.update(kwargs)
    return Contact(**args)


def test_reverse_rate_defaults_to_the_forward_rate():
    assert _contact().reverse_rate_bps == 1000.0
    assert _contact(rate_ba_bps=50.0).reverse_rate_bps == 50.0


def test_ion_csv_writes_each_direction_with_its_own_rate(tmp_path):
    plan = ContactPlan(
        contacts=[_contact(rate_ba_bps=50.0)], summary=[], start_et=0.0, stop_et=300.0
    )
    lines = plan.ToIonCsv(tmp_path / "plan.csv").read_text().splitlines()
    assert lines == [
        "a contact +100 +200 dtn:a dtn:b 1000",
        "a range +100 +200 dtn:a dtn:b 1.500000",
        "a contact +100 +200 dtn:b dtn:a 50",
        "a range +100 +200 dtn:b dtn:a 1.500000",
    ]
