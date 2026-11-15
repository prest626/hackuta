"""Pydantic v2 mirrors of contracts/*.schema.json. Field names match the schemas."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# int | float keeps JSON 81 as 81 and 80.5 as 80.5 so examples round-trip.
Num = int | float
Compartment = Annotated[
    str, Field(pattern=r"^(SUN|MON|TUE|WED|THU|FRI|SAT)-(AM|NOON|PM|BED)$")
]
Slot = Literal["AM", "NOON", "PM", "BED"]
Day = Literal["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
Metric = Literal["hr", "rhr", "hrv_sdnn", "rr_sleep", "spo2", "steps", "rr_cam"]
CallKind = Literal[
    "checkin", "nurse_callback", "clinician_group_call", "family_group_call"
]
Direction = Literal["outbound", "inbound"]
Tier = Literal["GREEN", "YELLOW", "RED"]
HHMM = Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
PatId = Annotated[str, Field(pattern=r"^pat_[a-z0-9]{4,32}$")]
CallId = Annotated[str, Field(pattern=r"^call_[a-z0-9]{4,40}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Contact handle: E.164, or an Apple ID email with no spaces, ';', quotes, or '/'.
_HANDLE = r"^(?:\+[1-9][0-9]{7,14}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$"


class Contact(Model):
    role: Literal["nurse", "clinician", "family"]
    name: str
    phone_e164: str = Field(pattern=_HANDLE)


class Consent(Model):
    calls: bool
    video_analysis: bool
    proof_frames: bool
    family_share: bool
    watch_vitals: bool


class SymptomQuestion(Model):
    slot: str = Field(pattern=r"^[a-z_]{2,40}$")
    prompt: str
    answer_type: Literal["yes_no", "better_same_worse", "scale_0_10", "free_text"]


class RedFlags(Model):
    urgent_911: list[str]
    call_care_team: list[str]


class Baseline(Model):
    rhr_bpm_mean: Num | None = None
    rhr_bpm_sd: Num | None = None
    source: Literal["mock", "hae", "watch"] | None = None


class Patient(Model):
    id: PatId
    is_mock: Literal[True]
    display_name: str = Field(min_length=1, max_length=60)
    phone_e164: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    tz: str = "America/Chicago"
    discharge_date: str
    condition_tag: Literal["hf", "copd", "pneumonia", "tka", "general"]
    checkin_days: list[Annotated[int, Field(ge=1, le=30)]] = Field(
        default_factory=lambda: [1, 2, 3, 4], min_length=1
    )
    checkin_local_time: HHMM = "10:00"
    contacts: list[Contact]
    consent: Consent
    symptom_questions: list[SymptomQuestion] = Field(min_length=1, max_length=5)
    red_flags: RedFlags
    watch_device_id: str | None
    baseline: Baseline | None = None


class ScheduleSlot(Model):
    slot: Slot
    local_time: HHMM


class Med(Model):
    name: str
    dose: str
    slots: list[Slot] = Field(min_length=1)
    instructions: str | None = None


class MedSchedule(Model):
    patient_id: PatId
    is_mock: Literal[True]
    organizer_layout: Literal["7x1", "7x2", "7x4"]
    week_starts_on: Literal["SUN", "MON"] = "SUN"
    slots: list[ScheduleSlot] = Field(min_length=1, max_length=4)
    meds: list[Med] = Field(min_length=1)
    start_date: str


class VitalSample(Model):
    t: str
    patient_id: PatId
    metric: Metric
    value: Num
    source: Literal["watch_workout", "hae", "camera", "mock_replay"]
    quality: Num | None = Field(default=None, ge=0, le=1)


class WatchHrSample(Model):
    t_end: str
    bpm: Num = Field(ge=30, le=220)
    source: Literal["workout", "mock_replay"] = "workout"


class WatchHrPost(Model):
    device_id: str = Field(min_length=4)
    samples: list[WatchHrSample] = Field(min_length=1, max_length=50)


class LiveVitals(Model):
    patient_id: str
    as_of: str
    hr_median_60s: Num | None
    hr_n_60s: int = Field(ge=0)
    hr_last_t: str | None
    stale: bool
    rhr_baseline_bpm: Num | None = None
    rhr_7d_bpm: Num | None = None
    rhr_z: Num | None = None
    steps_today: int | None = None
    hrv_sdnn_ms_last_night: Num | None = None
    rr_sleep_last_night: Num | None = None


class ObservedCompartment(Model):
    compartment: Compartment
    state: Literal["empty", "has_pills", "lid_closed", "not_visible"]
    bbox: list[Num] | None = Field(default=None, min_length=4, max_length=4)


class PillCheck(Model):
    state: Literal["ok", "missed_possible", "unknown", "skipped"]
    expected_empty: list[Compartment] | None = None
    observed: list[ObservedCompartment] | None = None
    mismatches: list[str] | None = None
    image_quality: Literal["good", "blurry", "glare", "too_far", "partial", "no_frame"] | None = None
    confidence: Num | None = Field(default=None, ge=0, le=1)
    retries: int | None = Field(default=None, ge=0, le=2)
    self_report: str | None = None
    proof_ref: str | None = None
    model: str | None = None


class SymptomAnswer(Model):
    slot: str
    value: str
    quote: str
    confirmed: bool = False


class Breathing(Model):
    mode: Literal["paced_measured", "self_count", "skipped", "abstained"]
    rate_per_min: Num | None = None
    sqi: Num | None = Field(default=None, ge=0, le=1)
    pacer_rate_per_min: Num | None = None
    note: str | None = None


class Frames(Model):
    received: bool | None = None
    fps_capture: Num | None = None
    width: int | None = None
    height: int | None = None
    source: Literal["window_capture", "fixture"] | None = None


class CallResult(Model):
    call_id: CallId
    patient_id: PatId
    kind: CallKind
    day_index: int = Field(ge=0, le=30)
    status: Literal["completed", "partial", "no_answer", "failed", "emergency_script"]
    started_at: str | None
    ended_at: str | None
    pill_check: PillCheck
    symptoms: list[SymptomAnswer]
    breathing: Breathing
    vitals_snapshot: LiveVitals
    emergency_script_given: bool
    end_reason: Literal[
        "agent_hangup", "hard_stop", "patient_hangup", "no_answer", "bridge_error", "error"
    ] | None = None
    agent_concern: str | None = Field(default=None, max_length=300)
    summary_text: str | None = Field(default=None, max_length=600)
    direction: Direction | None = None
    frames: Frames | None = None


class ScheduledCall(Model):
    id: CallId
    patient_id: str
    day_index: int
    kind: CallKind
    due_at: str
    status: Literal[
        "scheduled",
        "dialing",
        "ringing",
        "in_call",
        "done",
        "no_answer",
        "retry_wait",
        "failed",
        "cancelled",
    ]
    attempts: int = Field(ge=0)
    approval_id: str | None = None
    direction: Direction | None = None


class Flag(Model):
    id: str = Field(pattern=r"^flg_[a-z0-9]{4,40}$")
    patient_id: str
    call_id: str | None
    code: Literal[
        "emergency_script_given",
        "care_team_symptom",
        "symptom_worse_than_last_call",
        "missed_dose_possible",
        "pill_check_unknown",
        "hr_high_at_rest",
        "rhr_drift",
        "breathing_outside_wellness_range",
        "vitals_stale",
        "no_answer",
        "call_incomplete",
        "agent_concern",
    ]
    tier: Tier
    reason: str = Field(max_length=240)
    rule_id: str
    created_at: str
    status: Literal["open", "acknowledged", "resolved"]
    evidence: dict[str, Any] | None = None


class Decision(Model):
    decision: Literal["approve", "reject"]
    nurse_name: str = Field(min_length=2)
    decided_at: str
    action_override: Literal[
        "nurse_callback", "clinician_group_call", "family_group_call", "family_imessage"
    ] | None = None
    note: str | None = Field(default=None, max_length=300)


class Approval(Model):
    id: str = Field(pattern=r"^apr_[a-z0-9]{4,40}$")
    patient_id: str
    call_id: str | None
    flag_ids: list[str] = Field(min_length=1)
    tier: Literal["YELLOW", "RED"]
    action: Literal[
        "nurse_callback", "clinician_group_call", "family_group_call", "family_imessage"
    ]
    recipients: list[Literal["patient", "nurse", "clinician", "family"]] = Field(min_length=1)
    brief_text: str = Field(max_length=400)
    status: Literal[
        "pending", "approved", "rejected", "executing", "executed", "failed", "expired"
    ]
    created_at: str
    decision: Decision | None = None
    executed_call_id: str | None = None
    error: str | None = None
