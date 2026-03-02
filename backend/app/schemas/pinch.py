"""Pinch analysis schemas."""
from pydantic import BaseModel, Field


class PinchStream(BaseModel):
    name: str = ""
    supply_temp: float = Field(..., description="Supply temperature °C")
    target_temp: float = Field(..., description="Target temperature °C")
    heat_capacity_flow: float = Field(..., gt=0, description="mCp in kW/°C")
    stream_type: str = Field(default="", description="hot or cold, auto-detected if empty")


class PinchRequest(BaseModel):
    streams: list[PinchStream]
    dt_min: float = Field(default=10.0, ge=1, le=100, description="Minimum approach ΔT °C")


class CompositePoint(BaseModel):
    temperature: float
    enthalpy: float


class PinchResult(BaseModel):
    pinch_temperature: float | None = None
    q_heating_min: float = 0.0
    q_cooling_min: float = 0.0
    hot_composite: list[CompositePoint] = Field(default_factory=list)
    cold_composite: list[CompositePoint] = Field(default_factory=list)
    grand_composite: list[CompositePoint] = Field(default_factory=list)
    heat_cascade: list[dict[str, float]] = Field(default_factory=list)
    status: str = "success"
    error: str | None = None
