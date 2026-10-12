"""Local SQLite storage for the educational Smart Road MVP."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "smart_road.sqlite3"

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            samples INTEGER NOT NULL,
            max_vehicles INTEGER NOT NULL,
            max_pedestrians INTEGER NOT NULL,
            demo_index INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            light_raw INTEGER NOT NULL,
            obstacle INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")


def add_report(issue_type, severity, description, latitude, longitude):
    with connect() as db:
        db.execute(
            "INSERT INTO reports(issue_type,severity,description,latitude,longitude) VALUES(?,?,?,?,?)",
            (issue_type, severity, description.strip(), float(latitude), float(longitude)),
        )


def add_analysis(source, latitude, longitude, samples, max_vehicles, max_pedestrians, demo_index):
    with connect() as db:
        db.execute(
            "INSERT INTO analyses(source,latitude,longitude,samples,max_vehicles,max_pedestrians,demo_index) VALUES(?,?,?,?,?,?,?)",
            (source, latitude, longitude, samples, max_vehicles, max_pedestrians, demo_index),
        )


def add_sensor(light_raw, obstacle, latitude, longitude):
    with connect() as db:
        db.execute("INSERT INTO sensor_readings(light_raw,obstacle,latitude,longitude) VALUES(?,?,?,?)",
                   (light_raw, int(obstacle), latitude, longitude))


def fetch(table, limit=200):
    if table not in {"reports", "analyses", "sensor_readings"}:
        raise ValueError("Invalid table name")
    with connect() as db:
        return [dict(r) for r in db.execute(
            f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (int(limit),))]
