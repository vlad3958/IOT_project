from dataclasses import dataclass
from datetime import datetime


@dataclass
class ViolationEvent:
    violation_type: str
    zone_id: str
    timestamp: datetime
    gps_longitude: float
    gps_latitude: float
    message: str
