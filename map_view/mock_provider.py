import os
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AccelerometerData:
    x: float
    y: float
    z: float


@dataclass
class GPSPoint:
    longitude: float
    latitude: float


@dataclass
class RoadAnomaly:
    anomaly_type: str
    gps_point: GPSPoint
    intensity: float


class MockStoreProvider:
    GRAVITY = 16667
    BUMP_THRESHOLD = 500
    POTHOLES_THRESHOLD = -500
    
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = data_dir
        self.accelerometer_data: List[AccelerometerData] = []
        self.gps_data: List[GPSPoint] = []
        self._load_data()
    
    def _load_data(self):
        accel_path = os.path.join(self.data_dir, 'data.csv')
        if os.path.exists(accel_path):
            df = pd.read_csv(accel_path, header=None, names=['x', 'y', 'z'])
            df['x'] = pd.to_numeric(df['x'], errors='coerce')
            df['y'] = pd.to_numeric(df['y'], errors='coerce')
            df['z'] = pd.to_numeric(df['z'], errors='coerce')
            df = df.dropna()
            self.accelerometer_data = [
                AccelerometerData(float(row['x']), float(row['y']), float(row['z']))
                for _, row in df.iterrows()
            ]
        
        gps_paths = [
            os.path.join(self.data_dir, 'gps.csv'),
            os.path.join(self.data_dir, '..', 'agent', 'src', 'gps.csv'),
            os.path.join('agent', 'src', 'gps.csv'),
        ]
        
        for gps_path in gps_paths:
            if os.path.exists(gps_path):
                df = pd.read_csv(gps_path)
                if 'longitude' in df.columns and 'latitude' in df.columns:
                    self.gps_data = [
                        GPSPoint(row['longitude'], row['latitude'])
                        for _, row in df.iterrows()
                    ]
                    break
        
        if not self.gps_data:
            self._generate_synthetic_gps()
    
    def _generate_synthetic_gps(self):
        start_lon = 50.450386
        start_lat = 30.524547
        
        for i in range(len(self.accelerometer_data)):
            lon = start_lon - (i * 0.0001)
            lat = start_lat - (i * 0.0002)
            self.gps_data.append(GPSPoint(lon, lat))
    
    def get_all_data(self) -> List[Dict]:
        result = []
        gps_len = len(self.gps_data)
        accel_len = len(self.accelerometer_data)
        
        for i in range(max(gps_len, accel_len)):
            gps = self.gps_data[i % gps_len] if gps_len > 0 else GPSPoint(0, 0)
            accel = self.accelerometer_data[i % accel_len] if accel_len > 0 else AccelerometerData(0, 0, 0)
            
            result.append({
                'timestamp': i,
                'accelerometer': {
                    'x': accel.x,
                    'y': accel.y,
                    'z': accel.z
                },
                'gps': {
                    'longitude': gps.longitude,
                    'latitude': gps.latitude
                }
            })
        
        return result
    
    def get_data_batch(self, offset: int = 0, limit: int = 100) -> List[Dict]:
        all_data = self.get_all_data()
        return all_data[offset:offset + limit]
    
    def detect_road_anomalies(self) -> List[RoadAnomaly]:
        anomalies = []
        
        if not self.accelerometer_data or not self.gps_data:
            return anomalies
        
        z_values = np.array([d.z for d in self.accelerometer_data])
        normalized_z = z_values - self.GRAVITY
        
        bumps = self._find_peaks(normalized_z, self.BUMP_THRESHOLD)
        potholes = self._find_peaks(-normalized_z, -self.POTHOLES_THRESHOLD)
        
        for idx in bumps:
            if idx < len(self.gps_data):
                intensity = abs(normalized_z[idx]) / self.GRAVITY
                anomalies.append(RoadAnomaly(
                    anomaly_type='bump',
                    gps_point=self.gps_data[idx],
                    intensity=float(intensity)
                ))
        
        for idx in potholes:
            if idx < len(self.gps_data):
                intensity = abs(normalized_z[idx]) / self.GRAVITY
                anomalies.append(RoadAnomaly(
                    anomaly_type='pothole',
                    gps_point=self.gps_data[idx],
                    intensity=float(intensity)
                ))
        
        return anomalies
    
    def _find_peaks(self, signal: np.ndarray, threshold: float) -> List[int]:
        peaks = []
        window = 5
        
        for i in range(window, len(signal) - window):
            is_local_max = True
            for j in range(-window, window + 1):
                if j != 0 and signal[i] <= signal[i + j]:
                    is_local_max = False
                    break
            
            if is_local_max and abs(signal[i]) > threshold:
                too_close = False
                for p in peaks:
                    if abs(i - p) < window * 2:
                        too_close = True
                        break
                
                if not too_close:
                    peaks.append(i)
        
        return peaks
    
    def get_route_coordinates(self) -> List[Tuple[float, float]]:
        return [(gps.longitude, gps.latitude) for gps in self.gps_data]


_provider: Optional[MockStoreProvider] = None


def get_mock_provider() -> MockStoreProvider:
    global _provider
    if _provider is None:
        _provider = MockStoreProvider()
    return _provider


if __name__ == "__main__":
    provider = get_mock_provider()
    
    print(f"Loaded {len(provider.accelerometer_data)} accelerometer records")
    print(f"Loaded {len(provider.gps_data)} GPS records")
    
    anomalies = provider.detect_road_anomalies()
    print(f"Detected {len(anomalies)} road anomalies:")
    
    bumps = [a for a in anomalies if a.anomaly_type == 'bump']
    potholes = [a for a in anomalies if a.anomaly_type == 'pothole']
    
    print(f"  - Bumps: {len(bumps)}")
    print(f"  - Potholes: {len(potholes)}")
