from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ViolationEvent(BaseModel):
    violation_type: str
    severity: str = "warning"
    vehicle_id: str
    latitude: float
    longitude: float
    timestamp: datetime
    message: str
    fine_type: str | None = None
    fine_amount: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
