import json
import logging
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.entities.agent_data import AgentData
from app.entities.road_rule import RoadRule
from app.entities.traffic_light_zone import TrafficLightZone
from app.entities.violation_event import ViolationEvent


class ViolationDetector:
    def __init__(
        self,
        road_rules: list[RoadRule],
        traffic_light_zones: list[TrafficLightZone],
        vehicle_id: str,
        min_movement_distance_m: float = 5.0,
        wrong_way_max_random_interval_s: float = 30.0,
    ):
        self.road_rules = road_rules
        self.traffic_light_zones = traffic_light_zones
        self.vehicle_id = vehicle_id
        self.min_movement_distance_m = min_movement_distance_m
        self.wrong_way_max_random_interval_s = wrong_way_max_random_interval_s
        self._active_wrong_way_roads: set[str] = set()
        self._active_red_light_zones: set[str] = set()
        self._next_wrong_way_event_at: dict[str, datetime] = {}

    @classmethod
    def from_json(
        cls,
        roads_config_path: str,
        traffic_lights_config_path: str,
        vehicle_id: str,
        min_movement_distance_m: float = 5.0,
        wrong_way_max_random_interval_s: float = 30.0,
    ) -> "ViolationDetector":
        road_rules = cls._load_road_rules(roads_config_path)
        traffic_light_zones = cls._load_traffic_light_zones(traffic_lights_config_path)

        return cls(
            road_rules,
            traffic_light_zones,
            vehicle_id,
            min_movement_distance_m,
            wrong_way_max_random_interval_s,
        )

    @staticmethod
    def _load_road_rules(config_path: str) -> list[RoadRule]:
        path = Path(config_path)
        if not path.exists():
            logging.warning("Road rules config not found: %s", config_path)
            return []

        with path.open("r", encoding="utf-8") as file:
            raw_rules = json.load(file)

        road_rules = [RoadRule.model_validate(raw_rule) for raw_rule in raw_rules]
        logging.info("Loaded %s road rule(s) from %s", len(road_rules), config_path)
        return road_rules

    @staticmethod
    def _load_traffic_light_zones(config_path: str) -> list[TrafficLightZone]:
        path = Path(config_path)
        if not path.exists():
            logging.warning("Traffic lights config not found: %s", config_path)
            return []

        with path.open("r", encoding="utf-8") as file:
            raw_zones = json.load(file)

        zones = [
            TrafficLightZone.model_validate(raw_zone)
            for raw_zone in raw_zones
            if str(raw_zone.get("type", "")).lower() == "traffic_light"
        ]
        logging.info("Loaded %s traffic light zone(s) from %s", len(zones), config_path)
        return zones

    def detect(
        self,
        current_agent_data: AgentData,
        previous_agent_data: AgentData | None,
    ) -> list[ViolationEvent]:
        violations: list[ViolationEvent] = []
        violations.extend(
            self.detect_wrong_way_driving(
                current_agent_data=current_agent_data,
                previous_agent_data=previous_agent_data,
            )
        )
        violations.extend(
            self.detect_red_light_violation(
                current_agent_data=current_agent_data,
                previous_agent_data=previous_agent_data,
            )
        )
        return violations

    def detect_red_light_violation(
        self,
        current_agent_data: AgentData,
        previous_agent_data: AgentData | None,
    ) -> list[ViolationEvent]:
        if previous_agent_data is None or not self.traffic_light_zones:
            return []

        current_lon = current_agent_data.gps.longitude
        current_lat = current_agent_data.gps.latitude
        previous_lon = previous_agent_data.gps.longitude
        previous_lat = previous_agent_data.gps.latitude

        violations: list[ViolationEvent] = []
        active_zones_now: set[str] = set()

        for zone in self.traffic_light_zones:
            zone_lon, zone_lat = zone.center
            was_inside = self._distance_m(previous_lon, previous_lat, zone_lon, zone_lat) <= zone.radius_m
            current_distance_m = self._distance_m(current_lon, current_lat, zone_lon, zone_lat)
            is_inside = current_distance_m <= zone.radius_m

            if is_inside:
                active_zones_now.add(zone.zone_id)

            if str(zone.state).lower() != "red":
                continue

            if not was_inside and is_inside and zone.zone_id not in self._active_red_light_zones:
                violations.append(
                    ViolationEvent(
                        violation_type="red_light",
                        severity="major",
                        vehicle_id=self.vehicle_id,
                        latitude=current_lat,
                        longitude=current_lon,
                        timestamp=current_agent_data.timestamp,
                        message=(
                            "Зафіксовано проїзд на червоний сигнал світлофора. "
                            "Будь ласка, дотримуйтесь правил дорожнього руху"
                        ),
                        details={
                            "zone_id": zone.zone_id,
                            "signal_state": zone.state,
                            "distance_to_zone_m": round(current_distance_m, 2),
                            "zone_radius_m": zone.radius_m,
                        },
                    )
                )

        self._active_red_light_zones = active_zones_now
        return violations

    def detect_wrong_way_driving(
        self,
        current_agent_data: AgentData,
        previous_agent_data: AgentData | None,
    ) -> list[ViolationEvent]:
        if previous_agent_data is None or not self.road_rules:
            return []

        current_lon = current_agent_data.gps.longitude
        current_lat = current_agent_data.gps.latitude
        previous_lon = previous_agent_data.gps.longitude
        previous_lat = previous_agent_data.gps.latitude

        movement_distance = self._distance_m(
            previous_lon,
            previous_lat,
            current_lon,
            current_lat,
        )
        if movement_distance < self.min_movement_distance_m:
            return []

        current_rule, distance_to_rule = self._get_matching_road_rule(
            current_lon, current_lat)
        self._drop_inactive_wrong_way_violations(
            active_road_id=current_rule.road_id if current_rule else None)
        if current_rule is None:
            return []

        actual_bearing = self._bearing_deg(
            previous_lon, previous_lat, current_lon, current_lat)
        if actual_bearing is None:
            return []

        deviation_deg = self._angular_difference_deg(
            actual_bearing,
            current_rule.allowed_direction,
        )
        is_wrong_way = deviation_deg >= current_rule.wrong_way_threshold_deg
        if not is_wrong_way:
            self._clear_wrong_way_state(current_rule.road_id)
            return []

        next_event_at = self._next_wrong_way_event_at.get(current_rule.road_id)
        should_emit_event = False

        if current_rule.road_id not in self._active_wrong_way_roads:
            self._active_wrong_way_roads.add(current_rule.road_id)
            should_emit_event = True
        elif next_event_at is not None and current_agent_data.timestamp >= next_event_at:
            should_emit_event = True

        if not should_emit_event:
            return []

        next_interval_s = self._schedule_next_wrong_way_event(
            current_rule.road_id,
            current_agent_data.timestamp,
        )
        return [
            ViolationEvent(
                violation_type="wrong_way_driving",
                severity="major",
                vehicle_id=self.vehicle_id,
                latitude=current_lat,
                longitude=current_lon,
                timestamp=current_agent_data.timestamp,
                message=(
                    "Зафіксовано рух по зустрічній смузі. "
                    "Будь ласка, дотримуйтесь дозволеного напрямку руху."
                ),
                details={
                    "road_id": current_rule.road_id,
                    "actual_direction": round(actual_bearing, 2),
                    "allowed_direction": round(current_rule.allowed_direction, 2),
                    "direction_deviation_deg": round(deviation_deg, 2),
                    "distance_to_road_m": round(distance_to_rule, 2),
                    "road_radius_m": current_rule.radius_m,
                    "movement_distance_m": round(movement_distance, 2),
                    "next_random_interval_s": next_interval_s,
                },
            )
        ]

    def _get_matching_road_rule(
        self,
        longitude: float,
        latitude: float,
    ) -> tuple[RoadRule | None, float]:
        closest_rule: RoadRule | None = None
        closest_distance = math.inf

        for road_rule in self.road_rules:
            rule_lon, rule_lat = road_rule.center
            distance = self._distance_m(
                longitude, latitude, rule_lon, rule_lat)
            if distance <= road_rule.radius_m and distance < closest_distance:
                closest_rule = road_rule
                closest_distance = distance

        return closest_rule, closest_distance

    def _drop_inactive_wrong_way_violations(self, active_road_id: str | None):
        if active_road_id is None:
            self._active_wrong_way_roads.clear()
            self._next_wrong_way_event_at.clear()
            return

        inactive_road_ids = {
            road_id for road_id in self._active_wrong_way_roads if road_id != active_road_id
        }
        for road_id in inactive_road_ids:
            self._next_wrong_way_event_at.pop(road_id, None)

        self._active_wrong_way_roads = {
            road_id for road_id in self._active_wrong_way_roads if road_id == active_road_id
        }

    def _clear_wrong_way_state(self, road_id: str):
        self._active_wrong_way_roads.discard(road_id)
        self._next_wrong_way_event_at.pop(road_id, None)

    def _schedule_next_wrong_way_event(
        self,
        road_id: str,
        current_timestamp: datetime,
    ) -> float:
        max_interval_s = max(1.0, self.wrong_way_max_random_interval_s)
        next_interval_s = round(random.uniform(1.0, max_interval_s), 2)
        self._next_wrong_way_event_at[road_id] = (
            current_timestamp + timedelta(seconds=next_interval_s)
        )
        return next_interval_s

    @staticmethod
    def _distance_m(
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float,
    ) -> float:
        radius_m = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_m * c

    @staticmethod
    def _bearing_deg(
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float,
    ) -> float | None:
        if lon1 == lon2 and lat1 == lat2:
            return None

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)

        y = math.sin(delta_lambda) * math.cos(phi2)
        x = (
            math.cos(phi1) * math.sin(phi2)
            - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
        )
        return (math.degrees(math.atan2(y, x)) + 360) % 360

    @staticmethod
    def _angular_difference_deg(angle_a: float, angle_b: float) -> float:
        diff = abs(angle_a - angle_b) % 360
        return min(diff, 360 - diff)
