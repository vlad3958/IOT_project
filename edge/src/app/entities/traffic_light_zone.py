from pydantic import BaseModel, Field


class TrafficLightZone(BaseModel):
    zone_id: str
    type: str = "traffic_light"
    center: tuple[float, float]
    radius_m: float = Field(gt=0)
    state: str = "red"
