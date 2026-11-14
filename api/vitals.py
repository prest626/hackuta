"""Live vitals from the vitals table. Stale means do not quote the number as live."""

import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from api import db
from contracts.models import LiveVitals, Patient, VitalSample

_HR_WINDOW = timedelta(seconds=60)
_STALE_AFTER = timedelta(seconds=30)


def parse_t(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _fmt(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows(patient_id: str) -> list:
    with db.conn() as c:
        return c.execute(
            "SELECT t, patient_id, metric, value, source, quality FROM vitals "
            "WHERE patient_id = ? ORDER BY t DESC",
            (patient_id,),
        ).fetchall()


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def live_vitals(patient: Patient, now: datetime | None = None) -> LiveVitals:
    now = now or datetime.now(timezone.utc)
    rows = _rows(patient.id)
    hr = [(parse_t(r["t"]), r) for r in rows if r["metric"] == "hr" and parse_t(r["t"]) <= now]
    in_60 = [pair for pair in hr if now - pair[0] <= _HR_WINDOW]
    in_30 = [pair for pair in hr if now - pair[0] <= _STALE_AFTER]
    hr_values = [pair[1]["value"] for pair in in_60]
    median = statistics.median(hr_values) if hr_values else None
    last_t = max(in_60, key=lambda pair: pair[0])[1]["t"] if in_60 else None

    def metric_values(metric: str, window: timedelta) -> list[float]:
        return [r["value"] for r in rows if r["metric"] == metric and now - parse_t(r["t"]) <= window and parse_t(r["t"]) <= now]

    rhr_7 = metric_values("rhr", timedelta(days=7))
    rhr_60 = metric_values("rhr", timedelta(days=60))
    rhr_7d = _mean(rhr_7)
    baseline = patient.baseline
    base_mean = baseline.rhr_bpm_mean if baseline and baseline.rhr_bpm_mean is not None else _mean(rhr_60)
    base_sd = baseline.rhr_bpm_sd if baseline and baseline.rhr_bpm_sd is not None else None
    if base_sd is None and len(rhr_60) >= 2:
        base_sd = statistics.pstdev(rhr_60)
    rhr_z = None
    if rhr_7d is not None and base_mean is not None and base_sd:
        rhr_z = (rhr_7d - base_mean) / base_sd

    tz = ZoneInfo(patient.tz)
    today = now.astimezone(tz).date()
    steps = [
        r for r in rows
        if r["metric"] == "steps" and parse_t(r["t"]).astimezone(tz).date() == today and parse_t(r["t"]) <= now
    ]
    # shortcut: latest sample stands in for last night, upgrade = an overnight window
    hrv = next((r["value"] for r in rows if r["metric"] == "hrv_sdnn" and parse_t(r["t"]) <= now), None)
    rr = next((r["value"] for r in rows if r["metric"] == "rr_sleep" and parse_t(r["t"]) <= now), None)

    return LiveVitals(
        patient_id=patient.id,
        as_of=_fmt(now),
        hr_median_60s=median,
        hr_n_60s=len(in_60),
        hr_last_t=last_t,
        stale=not in_30,
        rhr_baseline_bpm=base_mean,
        rhr_7d_bpm=rhr_7d,
        rhr_z=rhr_z,
        steps_today=int(steps[0]["value"]) if steps else None,
        hrv_sdnn_ms_last_night=hrv,
        rr_sleep_last_night=rr,
    )


def history(patient_id: str, metric: str | None, since: str | None) -> list[dict]:
    since_dt = parse_t(since) if since else None
    out = []
    for row in _rows(patient_id):
        if metric and row["metric"] != metric:
            continue
        if since_dt and parse_t(row["t"]) < since_dt:
            continue
        sample = VitalSample.model_validate(
            {
                "t": row["t"],
                "patient_id": row["patient_id"],
                "metric": row["metric"],
                "value": row["value"],
                "source": row["source"],
                "quality": row["quality"],
            }
        )
        out.append(sample.model_dump(mode="json"))
    return out
