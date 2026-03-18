from datetime import datetime
from typing import Any, List, Set

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)
import json
import config
import uvicorn

# 1. Налаштування підключення до PostgreSQL
DATABASE_URL = f"postgresql+psycopg2://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}@{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# 2. Опис таблиць для бази даних
processed_agent_data = Table(
    "processed_agent_data",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("road_state", String),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime), 
)

parking_data_table = Table(
    "parking_data",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("empty_count", Integer),
    Column("latitude", Float),
    Column("longitude", Float),
)

violation_events = Table(
    "violation_events",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("violation_type", String, nullable=False),
    Column("severity", String),
    Column("vehicle_id", String),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
    Column("message", String),
    Column("fine_type", String),
    Column("fine_amount", Integer),
    Column("details", JSON),
)

# 3. Моделі даних Pydantic 
class AccelerometerData(BaseModel):
    x: float
    y: float
    z: float

class GpsData(BaseModel):
    longitude: float 
    latitude: float

class AgentData(BaseModel):
    accelerometer: AccelerometerData
    gps: GpsData
    timestamp: datetime 

    @field_validator('timestamp', mode='before')
    @classmethod
    def check_time(cls, value):
        if isinstance(value, datetime): 
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("Invalid time format. Expected ISO 8601.")

class ProcessedAgentData(BaseModel):
    road_state: str
    agent_data: AgentData

class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime


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

    @field_validator("timestamp", mode="before")
    @classmethod
    def check_violation_time(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("Invalid time format. Expected ISO 8601.")


class ViolationEventInDB(ViolationEvent):
    id: int


# 4. FastAPI додаток та WebSocket логіка
app = FastAPI(title="Road Monitoring Store API")
subscriptions: Set[WebSocket] = set()

@app.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscriptions.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        subscriptions.remove(websocket)

async def send_data_to_subscribers(data: List[dict]):
    for websocket in subscriptions:
        await websocket.send_json(data)

# 5. CRUD операції для Agent Data

@app.post("/processed_agent_data/", status_code=201)
async def create_processed_agent_data(data: List[ProcessedAgentData]):
    with engine.connect() as connection:
        inserted_data = []
        for item in data:
            stmt = processed_agent_data.insert().values(
                road_state=item.road_state,
                x=item.agent_data.accelerometer.x,
                y=item.agent_data.accelerometer.y,
                z=item.agent_data.accelerometer.z,
                latitude=item.agent_data.gps.latitude,
                longitude=item.agent_data.gps.longitude,
                timestamp=item.agent_data.timestamp
            ).returning(processed_agent_data)
            result = connection.execute(stmt)
            inserted_data.append(dict(result.first()._mapping))
        connection.commit()
        await send_data_to_subscribers([json.loads(json.dumps(d, default=str)) for d in inserted_data])
    return {"status": "ok", "count": len(inserted_data)}

@app.get("/processed_agent_data/", response_model=List[ProcessedAgentDataInDB])
def list_processed_agent_data(limit: int | None = Query(default=None, ge=1, le=5000)):
    with engine.connect() as connection:
        query = processed_agent_data.select()
        if limit is not None:
            query = query.order_by(processed_agent_data.c.id.desc()).limit(limit)
        result = connection.execute(query)
        rows = [dict(row._mapping) for row in result]
        if limit is not None:
            rows.reverse()
        return rows

@app.get("/processed_agent_data/{data_id}", response_model=ProcessedAgentDataInDB)
def read_processed_agent_data(data_id: int):
    with engine.connect() as connection:
        query = processed_agent_data.select().where(processed_agent_data.c.id == data_id)
        result = connection.execute(query).first()
        if not result:
            raise HTTPException(status_code=404, detail="Data not found")
        return dict(result._mapping)

@app.put("/processed_agent_data/{data_id}", response_model=ProcessedAgentDataInDB)
def update_processed_agent_data(data_id: int, data: ProcessedAgentData):
    with engine.connect() as connection:
        stmt = processed_agent_data.update().where(
            processed_agent_data.c.id == data_id
        ).values(
            road_state=data.road_state,
            x=data.agent_data.accelerometer.x,
            y=data.agent_data.accelerometer.y,
            z=data.agent_data.accelerometer.z,
            latitude=data.agent_data.gps.latitude,
            longitude=data.agent_data.gps.longitude,
            timestamp=data.agent_data.timestamp
        )
        result = connection.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data not found")
        connection.commit()
        return read_processed_agent_data(data_id)

@app.delete("/processed_agent_data/{data_id}", response_model=ProcessedAgentDataInDB)
def delete_processed_agent_data(data_id: int):
    with engine.connect() as connection:
        data_to_delete = read_processed_agent_data(data_id)
        stmt = processed_agent_data.delete().where(processed_agent_data.c.id == data_id)
        connection.execute(stmt)
        connection.commit()
        return data_to_delete


@app.post("/violation_events/", status_code=201)
async def create_violation_events(data: List[ViolationEvent]):
    with engine.connect() as connection:
        inserted_data = []
        for item in data:
            stmt = violation_events.insert().values(
                violation_type=item.violation_type,
                severity=item.severity,
                vehicle_id=item.vehicle_id,
                latitude=item.latitude,
                longitude=item.longitude,
                timestamp=item.timestamp,
                message=item.message,
                fine_type=item.fine_type,
                fine_amount=item.fine_amount,
                details=item.details,
            ).returning(violation_events)
            result = connection.execute(stmt)
            inserted_data.append(dict(result.first()._mapping))
        connection.commit()
    return {"status": "ok", "count": len(inserted_data)}


@app.get("/violation_events/", response_model=List[ViolationEventInDB])
def list_violation_events(limit: int | None = Query(default=None, ge=1, le=1000)):
    with engine.connect() as connection:
        query = violation_events.select()
        if limit is not None:
            query = query.order_by(violation_events.c.id.desc()).limit(limit)
        result = connection.execute(query)
        rows = [dict(row._mapping) for row in result]
        if limit is not None:
            rows.reverse()
        return rows


@app.get("/violation_events/{event_id}", response_model=ViolationEventInDB)
def read_violation_event(event_id: int):
    with engine.connect() as connection:
        query = violation_events.select().where(violation_events.c.id == event_id)
        result = connection.execute(query).first()
        if not result:
            raise HTTPException(status_code=404, detail="Violation event not found")
        return dict(result._mapping)

# 6. Точка входу для запуску
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
