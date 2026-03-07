import os
import sys
import math
import threading
from typing import List, Dict, Optional, Tuple
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty

try:
    from scipy.signal import find_peaks
    from scipy.ndimage import uniform_filter1d
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

from kivy_garden.mapview import MapMarker, MapView, MapLayer
from kivy.graphics import Color, Line
from kivy.graphics.context_instructions import Translate, Scale

from lineMapLayer import LineMapLayer

MOCK_MODE = False

STORE_API_HOST = os.environ.get("STORE_API_HOST", "localhost")
STORE_API_PORT = int(os.environ.get("STORE_API_PORT", "8000"))
STORE_API_BASE_URL = f"http://{STORE_API_HOST}:{STORE_API_PORT}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class StoreApiClient:
    """Client for interacting with the Store API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_all_data(self) -> List[Dict]:
        """Fetch all processed agent data from Store API"""
        try:
            response = self.session.get(f"{self.base_url}/processed_agent_data/")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching data: {response.status_code}")
                return []
        except Exception as e:
            print(f"Store API connection error: {e}")
            return []
    
    def get_recent_data(self, limit: int = 100) -> List[Dict]:
        """Fetch recent data from Store API"""
        try:
            response = self.session.get(f"{self.base_url}/processed_agent_data/")
            if response.status_code == 200:
                data = response.json()
                return data[-limit:] if len(data) > limit else data
            return []
        except Exception as e:
            print(f"Store API connection error: {e}")
            return []


class MapViewApp(App):
    status_text = StringProperty("Initializing...")
    
    GRAVITY = 16667
    BUMP_THRESHOLD = 500
    POTHOLES_THRESHOLD = 500
    
    def __init__(self, **kwargs):
        super().__init__()
        
        self.mapview: Optional[MapView] = None
        self.car_marker: Optional[MapMarker] = None
        self.route_layer: Optional[LineMapLayer] = None
        
        self.accelerometer_data: List[float] = []
        self.gps_data: List[Tuple[float, float]] = []
        self.anomaly_markers: List[MapMarker] = []
        
        self.current_index = 0
        self.route_coordinates: List[Tuple[float, float]] = []
        
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
            
        except Exception as e:
            print(f"Error initializing mock provider: {e}")
            self.status_text = f"Mock Error: {e}"
    
    def _load_mock_data(self):
        try:
            from mock_provider import get_mock_provider
            provider = get_mock_provider()
            
            all_data = provider.get_all_data()
            
            for record in all_data:
                gps = record.get('gps', {})
                accel = record.get('accelerometer', {})
                
                lon = gps.get('longitude', 0)
                lat = gps.get('latitude', 0)
                z = accel.get('z', self.GRAVITY)
                
                self.gps_data.append((lon, lat))
                self.accelerometer_data.append(z)
            
            self.route_coordinates = provider.get_route_coordinates()
            
        except Exception as e:
            print(f"Error loading mock data: {e}")
    
    def _init_store_api(self):
        self.status_text = f"Connecting to Store API at {STORE_API_BASE_URL}"
        
        if not REQUESTS_AVAILABLE:
            self.status_text = "Error: requests library not available"
            return
        
        self.store_client = StoreApiClient(STORE_API_BASE_URL)
        
        self._load_store_data()
    
    def _load_store_data(self):
        """Load data from Store API"""
        if not self.store_client:
            return
        
        self.status_text = "Fetching data from Store API..."
        
        data = self.store_client.get_all_data()
        
        if not data:
            self.status_text = "No data from Store API"
            return
        
        for record in data:
            lon = record.get('longitude', 0)
            lat = record.get('latitude', 0)
            z = record.get('z', self.GRAVITY)
            
            if lon and lat:
                self.gps_data.append((lon, lat))
                self.accelerometer_data.append(z)
        
        self.route_coordinates = list(self.gps_data)
        self.status_text = f"Loaded {len(self.gps_data)} points from Store"
    
    def refresh_from_store(self):
        """Refresh data from Store API"""
        if not MOCK_MODE and self.store_client:
            self._load_store_data()
    
    def on_start(self):
        self.route_layer = LineMapLayer(
            coordinates=self.route_coordinates if self.route_coordinates else None,
            color=[0, 0.5, 1, 0.8],
            width=3
        )
        if self.route_layer:
            self.mapview.add_layer(self.route_layer)
        
        if self.gps_data:
            start_lon, start_lat = self.gps_data[0]
            self.car_marker = MapMarker(
                lon=start_lon,
                lat=start_lat,
                source=os.path.join(BASE_DIR, 'images', 'car.png')
            )
            if self.car_marker:
                self.mapview.add_marker(self.car_marker)
        
        self.check_road_quality()
        
        if self.gps_data:
            start_lon, start_lat = self.gps_data[0]
            self.mapview.center_on(start_lat, start_lon)
            self.mapview.zoom = 17
        
        Clock.schedule_interval(self.update, 0.5)
    
    def update(self, *args):
        if not self.gps_data or self.current_index >= len(self.gps_data):
            self.current_index = 0
        
        lon, lat = self.gps_data[self.current_index]
        
        self.update_car_marker((lon, lat))
        
        self.current_index = (self.current_index + 1) % len(self.gps_data)
        
        progress = int((self.current_index / len(self.gps_data)) * 100)
        self.status_text = f"Position: {self.current_index}/{len(self.gps_data)} ({progress}%)"
    
    def check_road_quality(self):
        if not self.accelerometer_data:
            print("No accelerometer data to analyze")
            return
        
        z_values = self.accelerometer_data
        if PANDAS_AVAILABLE:
            z_values = pd.Series(z_values)
        
        normalized_z = [z - self.GRAVITY for z in z_values]
        
        if SCIPY_AVAILABLE:
            bumps, _ = find_peaks(normalized_z, height=self.BUMP_THRESHOLD, distance=10)
            potholes, _ = find_peaks([-x for x in normalized_z], height=self.POTHOLES_THRESHOLD, distance=10)
        else:
            bumps = self._simple_peak_detection(normalized_z, positive=True)
            potholes = self._simple_peak_detection(normalized_z, positive=False)
        
        for idx in bumps:
            if idx < len(self.gps_data):
                gps_point = self.gps_data[idx]
                self.set_bump_marker(gps_point)
        
        for idx in potholes:
            if idx < len(self.gps_data):
                gps_point = self.gps_data[idx]
                self.set_pothole_marker(gps_point)
        
        print(f"Road Quality Analysis:")
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
                if j != 0:
                    if positive:
                        if data[i] <= data[i + j]:
                            is_peak = False
                            break
                    else:
                        if data[i] >= data[i + j]:
                            is_peak = False
                            break
            
            if is_peak and abs(data[i]) > threshold:
                too_close = False
                for p in peaks:
                    if abs(i - p) < window * 2:
                        too_close = True
                        break
                if not too_close:
                    peaks.append(i)
        
        return peaks
    
    def update_car_marker(self, point: Tuple[float, float]):
        if self.car_marker:
            lon, lat = point
            self.car_marker.lon = lon
            self.car_marker.lat = lat
    
    def set_pothole_marker(self, point: Tuple[float, float]):
        lon, lat = point
        
        marker = MapMarker(
            lon=lon,
            lat=lat,
            source=os.path.join(BASE_DIR, 'images', 'pothole.png')
        )
        
        self.mapview.add_marker(marker)
        self.anomaly_markers.append(marker)
    
    def set_bump_marker(self, point: Tuple[float, float]):
        lon, lat = point
        
        marker = MapMarker(
            lon=lon,
            lat=lat,
            source=os.path.join(BASE_DIR, 'images', 'bump.png')
        )
        
        self.mapview.add_marker(marker)
        self.anomaly_markers.append(marker)
    
    def build(self):
        default_lat = 30.524547
        default_lon = 50.450386
        
        self.mapview = MapView(
            zoom=17,
            lat=default_lat,
            lon=default_lon
        )
        
        return self.mapview


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
