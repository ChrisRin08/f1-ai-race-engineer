from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ContractModel):
    status: Literal["ok"]


class EventSummary(ContractModel):
    name: str = Field(min_length=1)
    round_number: PositiveInt | None
    country: str | None
    location: str | None


class SessionIdentity(ContractModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)


class CircuitSummary(ContractModel):
    name: str = Field(min_length=1)


class SessionTiming(ContractModel):
    scheduled_start_utc: AwareDatetime
    total_laps: PositiveInt | None

    @field_validator("scheduled_start_utc")
    @classmethod
    def require_utc_offset(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("scheduled_start_utc must use a zero UTC offset")
        return value


class Participant(ContractModel):
    position: PositiveInt | None
    driver_number: str = Field(min_length=1)
    abbreviation: str | None
    full_name: str | None
    team_name: str | None


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"


class DataAvailability(ContractModel):
    session_info: AvailabilityStatus
    results: AvailabilityStatus
    laps: AvailabilityStatus
    telemetry: AvailabilityStatus
    weather: AvailabilityStatus
    race_control_messages: AvailabilityStatus


class SourceProvenance(ContractModel):
    provider: Literal["FastF1"]


class ErrorDetail(ContractModel):
    code: str
    message: str


class ErrorResponse(ContractModel):
    error: ErrorDetail


class SessionSummary(ContractModel):
    year: int
    event: EventSummary
    session: SessionIdentity
    circuit: CircuitSummary
    timing: SessionTiming
    participants: list[Participant]
    data_availability: DataAvailability
    source: SourceProvenance
