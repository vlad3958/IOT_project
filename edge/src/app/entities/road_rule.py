from pydantic import BaseModel, Field


class RoadRule(BaseModel):
    road_id: str
    center: tuple[float, float]
    radius_m: float = Field(gt=0)
    allowed_direction: float = Field(ge=0, lt=360)
    wrong_way_threshold_deg: float = Field(default=135.0, gt=0, le=180)
