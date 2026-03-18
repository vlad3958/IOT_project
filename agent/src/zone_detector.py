import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.gps import Gps
from domain.violation_event import ViolationEvent


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    earth_radius_m = 6371000.0

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_m * c


def _is_inside_zone(gps: Gps, zone: dict[str, Any]) -> bool:
    zone_lon, zone_lat = zone["center"]
    distance_m = _haversine_m(gps.longitude, gps.latitude, zone_lon, zone_lat)
    return distance_m <= float(zone["radius_m"])


def load_zones(zones_file_path: str) -> list[dict[str, Any]]:
    path = Path(zones_file_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / zones_file_path

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("zones.json must contain a JSON object or array")


def detect_red_light_violation(
    current_gps: Gps,
    previous_gps: Gps | None,
    zones: list[dict[str, Any]],
) -> list[ViolationEvent]:
    if previous_gps is None:
        return []

    violations: list[ViolationEvent] = []
    for zone in zones:
        if zone.get("type") != "traffic_light" or zone.get("state") != "red":
            continue

        was_inside = _is_inside_zone(previous_gps, zone)
        is_inside = _is_inside_zone(current_gps, zone)

        if not was_inside and is_inside:
            violations.append(
                ViolationEvent(
                    violation_type="red_light",
                    zone_id=str(zone.get("zone_id", "unknown_zone")),
                    timestamp=datetime.now(),
                    gps_longitude=current_gps.longitude,
                    gps_latitude=current_gps.latitude,
                    message=(
                        "Зафіксовано проїзд на червоний сигнал світлофора. "
                        "Будь ласка, дотримуйтесь правил дорожнього руху"
                    ),
                )
            )

    return violations
