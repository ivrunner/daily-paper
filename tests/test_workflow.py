"""The daily schedule must survive GitHub dropping a scheduled run."""
from pathlib import Path

import yaml

WORKFLOW = yaml.safe_load((Path(__file__).parent.parent / ".github/workflows/daily.yml").read_text())
TRIGGERS = WORKFLOW.get("on") or WORKFLOW[True]  # PyYAML reads the bare key `on` as True


def _crons():
    return [s["cron"] for s in TRIGGERS["schedule"]]


def test_schedule_avoids_the_top_of_the_hour():
    # GitHub drops scheduled runs most often at minute 0
    assert all(c.split()[0] != "0" for c in _crons())


def test_schedule_has_backup_attempts_inside_5_and_6_am_eastern_all_year():
    # UTC hour 9 = 5 AM EDT, hour 10 = 5 AM EST / 6 AM EDT; the gate accepts ET hours 05–06
    hours = [int(c.split()[1]) for c in _crons()]
    assert hours.count(9) >= 2 and hours.count(10) >= 2


def test_checkout_uses_latest_main_so_a_late_run_sees_todays_edition():
    steps = WORKFLOW["jobs"]["build"]["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert checkout.get("with", {}).get("ref") == "main"
