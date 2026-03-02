from csv import reader
from datetime import datetime
from domain.accelerometer import Accelerometer
from domain.gps import Gps
from domain.aggregated_data import AggregatedData

class FileDatasource:
    def __init__(self, accelerometer_filename: str, gps_filename: str, parking_filename: str) -> None:
        self.accelerometer_filename = accelerometer_filename
        self.gps_filename = gps_filename
        self.parking_filename = parking_filename
        self.accelerometer_data = []
        self.gps_data = []
        self.parking_data = []
        self.accel_index = 0
        self.gps_index = 0
        self.parking_index = 0

    def read(self):
        """Метод повертає дані отримані з датчиків та паркінгу як об'єкти AggregatedData і Parking"""
        from domain.parking import Parking
        if not self.accelerometer_data or not self.gps_data or not self.parking_data:
            return {
                'aggregated': AggregatedData(
                    accelerometer=Accelerometer(x=0, y=0, z=0),
                    gps=Gps(longitude=0.0, latitude=0.0),
                    time=datetime.now()
                ),
                'parking': Parking(empty_count=0, gps=None)
            }

        # Циклічне читання — коли дані закінчуються, починаємо спочатку
        accel = self.accelerometer_data[self.accel_index % len(self.accelerometer_data)]
        gps = self.gps_data[self.gps_index % len(self.gps_data)]
        parking_row = self.parking_data[self.parking_index % len(self.parking_data)]

        self.accel_index += 1
        self.gps_index += 1
        self.parking_index += 1

        aggregated = AggregatedData(
            accelerometer=Accelerometer(x=int(accel[0]), y=int(accel[1]), z=int(accel[2])),
            gps=Gps(longitude=float(gps[0]), latitude=float(gps[1])),
            time=datetime.now()
        )

        parking = Parking(
            empty_count=int(parking_row[0]),
            gps=Gps(longitude=float(parking_row[1]), latitude=float(parking_row[2]))
        )

        return {
            'aggregated': aggregated,
            'parking': parking
        }

    def startReading(self, *args, **kwargs):
        """Метод повинен викликатись перед початком читання даних"""
        # Читаємо accelerometer.csv
        with open(self.accelerometer_filename, 'r') as f:
            csv_reader = reader(f)
            next(csv_reader)  # Пропускаємо заголовок
            self.accelerometer_data = list(csv_reader)

        # Читаємо gps.csv
        with open(self.gps_filename, 'r') as f:
            csv_reader = reader(f)
            next(csv_reader)  # Пропускаємо заголовок
            self.gps_data = list(csv_reader)

        # Читаємо parking.csv
        with open(self.parking_filename, 'r') as f:
            csv_reader = reader(f)
            next(csv_reader)  # Пропускаємо заголовок
            self.parking_data = list(csv_reader)

        self.accel_index = 0
        self.gps_index = 0
        self.parking_index = 0

    def stopReading(self, *args, **kwargs):
        """Метод повинен викликатись для закінчення читання даних"""
        self.accelerometer_data = []
        self.gps_data = []
        self.parking_data = []