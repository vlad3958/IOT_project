import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

try:
    from scipy.signal import find_peaks

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available, using fallback peak detection")

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available")

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from kivy_garden.mapview import MapMarker, MapView

from lineMapLayer import LineMapLayer

MOCK_MODE = False

STORE_API_HOST = os.environ.get("STORE_API_HOST", "localhost")
STORE_API_PORT = int(os.environ.get("STORE_API_PORT", "8000"))
STORE_API_BASE_URL = f"http://{STORE_API_HOST}:{STORE_API_PORT}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class StoreApiClient:
    """Client for interacting with the Store API."""

    REQUEST_TIMEOUT_S = 5

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def get_all_data(self, limit: Optional[int] = None) -> List[Dict]:
        try:
            params = {"limit": limit} if limit else None
            response = self.session.get(
                f"{self.base_url}/processed_agent_data/",
                params=params,
                timeout=self.REQUEST_TIMEOUT_S,
            )
            if response.status_code == 200:
                return response.json()
            print(f"Error fetching processed data: {response.status_code}")
            return []
        except Exception as exc:
            print(f"Store API connection error: {exc}")
            return []

    def get_violation_events(self, limit: Optional[int] = None) -> List[Dict]:
        try:
            params = {"limit": limit} if limit else None
            response = self.session.get(
                f"{self.base_url}/violation_events/",
                params=params,
                timeout=self.REQUEST_TIMEOUT_S,
            )
            if response.status_code == 200:
                return response.json()
            print(f"Error fetching violations: {response.status_code}")
            return []
        except Exception as exc:
            print(f"Violation API connection error: {exc}")
            return []


class MapViewApp(App):
    status_text = StringProperty("Initializing...")
    warning_text = StringProperty("")

    GRAVITY = 16667
    BUMP_THRESHOLD = 500
    POTHOLES_THRESHOLD = 500
    REFRESH_INTERVAL_S = 1
    LIVE_ROUTE_POINT_LIMIT = 240
    LIVE_VIOLATION_LIMIT = 60
    MAX_ANOMALY_MARKERS_PER_TYPE = 12
    ANOMALY_MIN_INDEX_GAP = 10
    WARNING_DISPLAY_DURATION_S = 4

    def __init__(self, **kwargs):
        super().__init__()

        self.root_layout: Optional[BoxLayout] = None
        self.mapview: Optional[MapView] = None
        self.car_marker: Optional[MapMarker] = None
        self.route_layer: Optional[LineMapLayer] = None

        self.accelerometer_data: List[float] = []
        self.gps_data: List[Tuple[float, float]] = []
        self.gps_record_ids: List[int] = []
        self.anomaly_markers: List[MapMarker] = []
        self.violation_markers: List[MapMarker] = []

        self.current_index = 0
        self.route_coordinates: List[Tuple[float, float]] = []
        self.known_violation_ids: set[int] = set()
        self.latest_violation: Optional[Dict] = None
        self.violation_events_by_id: Dict[int, Dict] = {}
        self.warning_visible_until: float = 0.0
        self.last_anomaly_signature: Optional[Tuple[Tuple[int, ...],
                                                    Tuple[int, ...]]] = None

        self.store_client: Optional[StoreApiClient] = None

        if MOCK_MODE:
            self._init_mock_provider()
        else:
            self._init_store_api()

    def _init_mock_provider(self):
        self.status_text = "Using Mock Data Mode"

        try:
            from mock_provider import get_mock_provider

            self.mock_provider = get_mock_provider()
            self._load_mock_data()
            self.status_text = f"Loaded {len(self.gps_data)} GPS points (Mock)"
        except Exception as exc:
            print(f"Error initializing mock provider: {exc}")
            self.status_text = f"Mock Error: {exc}"

    def _load_mock_data(self):
        try:
            from mock_provider import get_mock_provider

            provider = get_mock_provider()
            all_data = provider.get_all_data()

            self.gps_data = []
            self.accelerometer_data = []
            for record in all_data:
                gps = record.get("gps", {})
                accel = record.get("accelerometer", {})

                lon = gps.get("longitude", 0)
                lat = gps.get("latitude", 0)
                z = accel.get("z", self.GRAVITY)

                self.gps_data.append((lon, lat))
                self.accelerometer_data.append(z)

            self.route_coordinates = list(provider.get_route_coordinates())
        except Exception as exc:
            print(f"Error loading mock data: {exc}")

    def _init_store_api(self):
        self.status_text = f"Connecting to Store API at {STORE_API_BASE_URL}"

        if not REQUESTS_AVAILABLE:
            self.status_text = "Error: requests library not available"
            return

        self.store_client = StoreApiClient(STORE_API_BASE_URL)
        self.refresh_from_store(initial_load=True)

    def _load_store_data(self):
        if not self.store_client:
            return

        processed_data = self.store_client.get_all_data(
            limit=self.LIVE_ROUTE_POINT_LIMIT,
        )
        processed_data = processed_data[-self.LIVE_ROUTE_POINT_LIMIT:]
        if not processed_data:
            self.gps_data = []
            self.gps_record_ids = []
            self.accelerometer_data = []
            self.route_coordinates = []
            self.status_text = "No route data from Store API"
            return

        rows: List[Tuple[int, float, float, float]] = []
        for record in processed_data:
            record_id = record.get("id")
            lon = record.get("longitude", 0)
            lat = record.get("latitude", 0)
            z = record.get("z", self.GRAVITY)

            if record_id is not None and lon and lat:
                rows.append((int(record_id), lon, lat, z))

        if not rows:
            self.gps_data = []
            self.gps_record_ids = []
            self.accelerometer_data = []
            self.route_coordinates = []
            self.status_text = "No valid GPS data from Store API"
            return

        if not self.gps_record_ids:
            self.gps_record_ids = [record_id for record_id, *_ in rows]
            self.gps_data = [(lon, lat) for _, lon, lat, _ in rows]
            self.accelerometer_data = [z for _, _, _, z in rows]
            self.route_coordinates = list(self.gps_data)
            self.current_index = 0
        else:
            latest_known_id = self.gps_record_ids[-1]
            new_rows = [row for row in rows if row[0] > latest_known_id]

            if rows[-1][0] < latest_known_id:
                self.gps_record_ids = [record_id for record_id, *_ in rows]
                self.gps_data = [(lon, lat) for _, lon, lat, _ in rows]
                self.accelerometer_data = [z for _, _, _, z in rows]
                self.route_coordinates = list(self.gps_data)
                self.current_index = 0
            elif new_rows:
                self.gps_record_ids.extend(record_id for record_id, *_ in new_rows)
                self.gps_data.extend((lon, lat) for _, lon, lat, _ in new_rows)
                self.accelerometer_data.extend(z for _, _, _, z in new_rows)
                self.route_coordinates = list(self.gps_data)

                overflow = len(self.gps_data) - self.LIVE_ROUTE_POINT_LIMIT
                if overflow > 0:
                    self.gps_record_ids = self.gps_record_ids[overflow:]
                    self.gps_data = self.gps_data[overflow:]
                    self.accelerometer_data = self.accelerometer_data[overflow:]
                    self.route_coordinates = self.route_coordinates[overflow:]
                    self.current_index = max(0, self.current_index - overflow)

        if self.gps_data:
            self.current_index = min(self.current_index, len(self.gps_data) - 1)
        else:
            self.current_index = 0
        latest_time = self._format_event_time(
            processed_data[-1].get("timestamp"))
        self.status_text = (
            f"Live: {len(self.gps_data)} visible points, latest sample at {latest_time}"
        )

    def _load_violation_events(self):
        if not self.store_client:
            return

        violation_events = self.store_client.get_violation_events(
            limit=self.LIVE_VIOLATION_LIMIT,
        )
        violation_events = violation_events[-self.LIVE_VIOLATION_LIMIT:]
        if not violation_events:
            return

        latest_events_by_id: Dict[int, Dict] = {}
        rerender_needed = set(self.violation_events_by_id) != {
            event.get("id") for event in violation_events if event.get("id") is not None
        }

        for event in violation_events:
            event_id = event.get("id")
            if event_id is None:
                continue
            event_with_display_coords = dict(event)
            previous_event = self.violation_events_by_id.get(event_id)
            if previous_event:
                if "display_longitude" in previous_event:
                    event_with_display_coords["display_longitude"] = previous_event["display_longitude"]
                if "display_latitude" in previous_event:
                    event_with_display_coords["display_latitude"] = previous_event["display_latitude"]
            else:
                current_vehicle_point = self._get_current_vehicle_point()
                if current_vehicle_point is not None:
                    event_with_display_coords["display_longitude"] = current_vehicle_point[0]
                    event_with_display_coords["display_latitude"] = current_vehicle_point[1]

            latest_events_by_id[event_id] = event_with_display_coords
            if event_id in self.known_violation_ids:
                continue
            self.known_violation_ids.add(event_id)
            self._show_violation_warning(event_with_display_coords)
            rerender_needed = True

        self.violation_events_by_id = latest_events_by_id
        if rerender_needed:
            self._render_existing_violation_markers()

    def refresh_from_store(self, initial_load: bool = False):
        if MOCK_MODE or not self.store_client:
            return

        self._load_store_data()
        self._load_violation_events()

        if self.route_layer:
            self.route_layer.coordinates = list(
                self.route_coordinates) if self.route_coordinates else None
        if self.mapview and self.gps_data:
            self.check_road_quality()
        if initial_load:
            return
        if self.mapview and self.gps_data:
            self._ensure_car_marker()
        self._expire_warning_if_needed()

    def on_start(self):
        self.route_layer = LineMapLayer(
            coordinates=self.route_coordinates if self.route_coordinates else None,
            color=[0, 0.5, 1, 0.8],
            width=3,
        )
        if self.route_layer and self.mapview:
            self.mapview.add_layer(self.route_layer)

        self._ensure_car_marker()
        self.check_road_quality()
        self._render_existing_violation_markers()
        self._center_map_on_route()

        Clock.schedule_interval(self.update, 0.5)
        if not MOCK_MODE:
            Clock.schedule_interval(
                lambda *_: self.refresh_from_store(),
                self.REFRESH_INTERVAL_S,
            )

    def _ensure_car_marker(self):
        if not self.mapview or not self.gps_data or self.car_marker:
            return

        start_lon, start_lat = self.gps_data[0]
        self.car_marker = MapMarker(
            lon=start_lon,
            lat=start_lat,
            source=os.path.join(BASE_DIR, "images", "car.png"),
        )
        self.mapview.add_marker(self.car_marker)

    def _center_map_on_route(self):
        if not self.mapview or not self.gps_data:
            return

        start_lon, start_lat = self.gps_data[0]
        self.mapview.center_on(start_lat, start_lon)
        self.mapview.zoom = 17

    def update(self, *args):
        self._expire_warning_if_needed()
        if not self.gps_data:
            self.status_text = "Очікування телеметрії з Store API..."
            return

        if self.current_index >= len(self.gps_data):
            self.current_index = 0

        lon, lat = self.gps_data[self.current_index]
        self.update_car_marker((lon, lat))

        self.current_index = (self.current_index + 1) % len(self.gps_data)
        progress = int((self.current_index / len(self.gps_data)) * 100)
        self.status_text = f"Position: {self.current_index}/{len(self.gps_data)} ({progress}%)"

    def _get_current_vehicle_point(self) -> Optional[Tuple[float, float]]:
        if not self.gps_data:
            return None
        safe_index = min(self.current_index, len(self.gps_data) - 1)
        return self.gps_data[safe_index]

    def check_road_quality(self):
        if not self.accelerometer_data:
            print("No accelerometer data to analyze")
            return

        z_values = self.accelerometer_data
        if PANDAS_AVAILABLE:
            z_values = pd.Series(z_values)

        normalized_z = [z - self.GRAVITY for z in z_values]

        if SCIPY_AVAILABLE:
            bumps, _ = find_peaks(
                normalized_z,
                height=self.BUMP_THRESHOLD,
                distance=10,
            )
            potholes, _ = find_peaks(
                [-value for value in normalized_z],
                height=self.POTHOLES_THRESHOLD,
                distance=10,
            )
        else:
            bumps = self._simple_peak_detection(normalized_z, positive=True)
            potholes = self._simple_peak_detection(
                normalized_z, positive=False)

        bumps = self._limit_peak_markers(bumps)
        potholes = self._limit_peak_markers(potholes)
        anomaly_signature = (tuple(bumps), tuple(potholes))
        if anomaly_signature == self.last_anomaly_signature:
            return
        self.last_anomaly_signature = anomaly_signature

        for marker in self.anomaly_markers:
            if self.mapview:
                self.mapview.remove_marker(marker)
        self.anomaly_markers = []

        for idx in bumps:
            if idx < len(self.gps_data):
                self.set_bump_marker(self.gps_data[idx])

        for idx in potholes:
            if idx < len(self.gps_data):
                self.set_pothole_marker(self.gps_data[idx])

        print("Road Quality Analysis:")
        print(f"  - Total data points: {len(z_values)}")
        print(f"  - Bumps detected: {len(bumps)}")
        print(f"  - Potholes detected: {len(potholes)}")

    def _simple_peak_detection(self, data: List[float], positive: bool = True) -> List[int]:
        peaks = []
        threshold = self.BUMP_THRESHOLD if positive else self.POTHOLES_THRESHOLD
        window = 5

        for i in range(window, len(data) - window):
            is_peak = True
            for j in range(-window, window + 1):
                if j == 0:
                    continue
                if positive and data[i] <= data[i + j]:
                    is_peak = False
                    break
                if not positive and data[i] >= data[i + j]:
                    is_peak = False
                    break

            if is_peak and abs(data[i]) > threshold:
                too_close = False
                for peak in peaks:
                    if abs(i - peak) < window * 2:
                        too_close = True
                        break
                if not too_close:
                    peaks.append(i)

        return peaks

    def _limit_peak_markers(self, peaks: List[int]) -> List[int]:
        selected: List[int] = []

        for idx in reversed(peaks):
            if any(abs(idx - existing) < self.ANOMALY_MIN_INDEX_GAP for existing in selected):
                continue
            selected.append(idx)
            if len(selected) >= self.MAX_ANOMALY_MARKERS_PER_TYPE:
                break

        selected.reverse()
        return selected

    def update_car_marker(self, point: Tuple[float, float]):
        if not self.mapview:
            return

        lon, lat = point

        if self.car_marker:
            self.mapview.remove_marker(self.car_marker)

        self.car_marker = MapMarker(
            lon=lon,
            lat=lat,
            source=os.path.join(BASE_DIR, "images", "car.png"),
        )
        self.mapview.add_marker(self.car_marker)
        self.mapview.trigger_update(False)
        self.mapview.canvas.ask_update()

    def set_pothole_marker(self, point: Tuple[float, float]):
        if not self.mapview:
            return

        lon, lat = point
        marker = MapMarker(
            lon=lon,
            lat=lat,
            source=os.path.join(BASE_DIR, "images", "pothole.png"),
        )
        self.mapview.add_marker(marker)
        self.anomaly_markers.append(marker)

    def set_bump_marker(self, point: Tuple[float, float]):
        if not self.mapview:
            return

        lon, lat = point
        marker = MapMarker(
            lon=lon,
            lat=lat,
            source=os.path.join(BASE_DIR, "images", "bump.png"),
        )
        self.mapview.add_marker(marker)
        self.anomaly_markers.append(marker)

    def _add_violation_marker(self, event: Dict):
        if not self.mapview:
            return

        lon = event.get("display_longitude", event.get("longitude"))
        lat = event.get("display_latitude", event.get("latitude"))
        if lon is None or lat is None:
            return

        marker = MapMarker(lon=lon, lat=lat)
        self.mapview.add_marker(marker)
        self.violation_markers.append(marker)

    def _render_existing_violation_markers(self):
        for marker in self.violation_markers:
            if self.mapview:
                self.mapview.remove_marker(marker)
        self.violation_markers = []

        for event_id in sorted(self.violation_events_by_id):
            self._add_violation_marker(self.violation_events_by_id[event_id])

    def _show_violation_warning(self, event: Dict):
        self.latest_violation = event
        self.warning_text = self._format_violation_message(event)
        now = time.monotonic()
        self.warning_visible_until = now + self.WARNING_DISPLAY_DURATION_S

    def _expire_warning_if_needed(self):
        if self.warning_text and time.monotonic() >= self.warning_visible_until:
            self.warning_text = ""

    @staticmethod
    def _format_violation_message(event: Dict) -> str:
        details = event.get("details", {}) or {}
        violation_type = event.get("violation_type", "unknown")
        event_time = MapViewApp._format_event_time(event.get("timestamp"))

        if violation_type == "wrong_way_driving":
            road_id = details.get("road_id", "unknown_road")
            actual_direction = details.get("actual_direction", "?")
            allowed_direction = details.get("allowed_direction", "?")
            return (
                f"[{event_time}] Зафіксовано рух по зустрічній смузі "
                f"на ділянці {road_id}. Фактичний напрямок: {actual_direction}°, "
                f"дозволений: {allowed_direction}°. Будь ласка, дотримуйтесь дозволеного напрямку руху."
            )

        return f"[{event_time}] {event.get('message', 'Отримано нове попередження про порушення.')}"

    @staticmethod
    def _format_event_time(raw_timestamp: Optional[str]) -> str:
        if not raw_timestamp:
            return "--:--:--"

        normalized_timestamp = raw_timestamp.replace("Z", "+00:00")
        try:
            event_dt = datetime.fromisoformat(normalized_timestamp)
            return event_dt.strftime("%H:%M:%S")
        except ValueError:
            return raw_timestamp

    def _build_status_label(
        self,
        text_property_name: str,
        height: int,
    ) -> Label:
        label = Label(
            text=getattr(self, text_property_name),
            size_hint=(1, None),
            height=height,
            halign="left",
            valign="middle",
            padding=(16, 10),
        )
        label.bind(
            size=lambda instance, value: setattr(instance, "text_size", value),
        )
        self.bind(
            **{
                text_property_name: (
                    lambda instance, value, target=label: setattr(
                        target, "text", value)
                )
            }
        )
        return label

    def build(self):
        default_lat = 30.524547
        default_lon = 50.450386

        self.root_layout = BoxLayout(
            orientation="vertical", spacing=4, padding=4)
        warning_label = self._build_status_label("warning_text", 78)
        status_label = self._build_status_label("status_text", 46)

        self.mapview = MapView(
            zoom=17,
            lat=default_lat,
            lon=default_lon,
        )

        self.root_layout.add_widget(warning_label)
        self.root_layout.add_widget(status_label)
        self.root_layout.add_widget(self.mapview)
        return self.root_layout


def main():
    print("=" * 50)
    print("Road Quality MapView Application")
    print("=" * 50)
    print(f"Mode: {'MOCK' if MOCK_MODE else 'LIVE STORE API'}")
    print(f"Store API: {STORE_API_BASE_URL}")
    print(f"Scipy available: {SCIPY_AVAILABLE}")
    print(f"Pandas available: {PANDAS_AVAILABLE}")
    print("=" * 50)

    MapViewApp().run()


if __name__ == "__main__":
    main()
