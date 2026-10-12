"""Optional LAN-only ESP32 receiver. Run `uvicorn receiver:app --host 0.0.0.0 --port 8000`."""
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from database import init_db, add_sensor

app = FastAPI(title="Smart Road - Classroom Sensor Receiver")
init_db()
SECRET = os.environ.get("ROAD_DEMO_KEY")

class Reading(BaseModel):
    light_raw: int = Field(ge=0, le=4095)
    obstacle: bool
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

@app.post("/sensor")
def sensor(reading: Reading, x_demo_key: str = Header(default="")):
    if not SECRET or x_demo_key != SECRET:
        raise HTTPException(401, "Bad demo key")
    add_sensor(reading.light_raw, reading.obstacle, reading.latitude, reading.longitude)
    return {"saved": True}
