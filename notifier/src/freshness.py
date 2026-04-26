from datetime import datetime, timedelta, timezone


class StaleDataError(RuntimeError):
    pass


def assert_fresh(file_mtime_utc: datetime, max_age_hours: int = 24) -> None:
    """Raise StaleDataError if file_mtime_utc is older than max_age_hours."""
    age = datetime.now(timezone.utc) - file_mtime_utc
    if age > timedelta(hours=max_age_hours):
        raise StaleDataError(
            f"MachineWeekSummary.csv is {age} old (max {max_age_hours}h). "
            "Aborting — Qlik reload may not have run."
        )
