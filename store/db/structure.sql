-- Таблиця для збереження оброблених даних від агента
CREATE TABLE processed_agent_data (
    id SERIAL PRIMARY KEY,
    road_state VARCHAR(255) NOT NULL,
    x FLOAT,
    y FLOAT,
    z FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    timestamp TIMESTAMP 
);

-- Таблиця для збереження даних про паркування 
CREATE TABLE parking_data (
    id SERIAL PRIMARY KEY,
    empty_count INTEGER,
    latitude FLOAT,
    longitude FLOAT
);

CREATE TABLE violation_events (
    id SERIAL PRIMARY KEY,
    violation_type VARCHAR(255) NOT NULL,
    severity VARCHAR(255),
    vehicle_id VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT,
    timestamp TIMESTAMP,
    message TEXT,
    fine_type VARCHAR(255),
    fine_amount INTEGER,
    details JSONB
);
