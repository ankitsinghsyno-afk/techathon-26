"""
FastAPI Server & Web Dashboard for Smart Office Energy & Occupancy Management.
Serves WebSockets, MJPEG video streaming, REST APIs, and the interactive dashboard.
"""
import os
import json
import asyncio
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.pipeline import FloorEnergyPipeline

app = FastAPI(title="Smart Office AI Energy Management System", version="1.0.0")

# Mount frontend directory for static assets
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

# Initialize pipeline with synthetic mode by default for zero-setup demonstration
pipeline = FloorEnergyPipeline(config_path="config/default_zones.json", source="synthetic")

# Active WebSocket connections
connected_websockets: List[WebSocket] = []


class ScenarioRequest(BaseModel):
    scenario: str  # "only_team_a", "only_team_b", "all_empty", "meeting_in_session", "all_occupied"


class OverrideRequest(BaseModel):
    zone_id: str
    lights_state: bool


class SensorTriggerRequest(BaseModel):
    zone_id: str
    motion: bool = True


class SourceRequest(BaseModel):
    source: str  # "synthetic", "0", "1", or RTSP url


@app.on_event("startup")
async def startup_event():
    # Background worker to drive the vision & telemetry loop
    asyncio.create_task(pipeline_background_worker())


async def pipeline_background_worker():
    """
    Continuous loop updating vision inference, state machines, and broadcasting telemetry.
    """
    while pipeline.is_running:
        try:
            telemetry = pipeline.process_tick()
            if telemetry and connected_websockets:
                payload = telemetry.model_dump_json()
                disconnected = []
                for ws in connected_websockets:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    if ws in connected_websockets:
                        connected_websockets.remove(ws)
        except Exception as e:
            print(f"Error in pipeline loop: {e}")
        # Dynamic low-latency loop
        await asyncio.sleep(0.015)


@app.get("/api/stream")
def video_feed():
    """
    Live MJPEG streaming endpoint for camera feed with AI bounding boxes and zone overlay.
    """
    def iter_frames():
        while True:
            if pipeline.latest_frame_jpeg is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + pipeline.latest_frame_jpeg + b"\r\n"
                )
            time.sleep(0.025)

    return StreamingResponse(
        iter_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/status")
def get_status():
    """Returns the latest floor telemetry snapshot."""
    if pipeline.latest_telemetry:
        return pipeline.latest_telemetry.model_dump()
    return {"status": "initializing"}


@app.post("/api/scenario")
def trigger_scenario(req: ScenarioRequest):
    """
    Quickly tests realistic office scenarios:
    - only_team_a (solves the user's specific prompt!)
    - only_team_b
    - all_empty
    - meeting_in_session
    - all_occupied
    """
    valid = [
        "only_bay_1", "only_bay_2", "bays_1_and_3", "conference_meeting",
        "all_occupied", "all_empty", "only_team_a", "only_team_b", "meeting_in_session"
    ]
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Choose from {valid}")

    pipeline.switch_scenario(req.scenario)
    return {"success": True, "scenario": req.scenario}


@app.post("/api/override")
def manual_override(req: OverrideRequest):
    """Manually turns lights ON or OFF for a specific zone."""
    if req.zone_id not in pipeline.zone_manager.zones:
        raise HTTPException(status_code=404, detail="Zone not found")

    zone = pipeline.zone_manager.zones[req.zone_id]
    zone.lights_state = req.lights_state
    for app_item in zone.appliances:
        if app_item.type in ("light", "display", "socket"):
            app_item.is_active = req.lights_state

    pipeline.switch_controller.batch_update_zone(
        switches=[a.switch_id for a in zone.appliances],
        state=req.lights_state,
        zone_name=zone.name,
        reason="Manual Dashboard Override"
    )
    return {"success": True, "zone_id": req.zone_id, "lights_state": req.lights_state}


@app.post("/api/source")
def change_video_source(req: SourceRequest):
    """Switches between synthetic simulation, webcam index (0), or RTSP/HTTP feed."""
    global pipeline
    from src.video_stream import VideoStreamHandler
    pipeline.stream_handler.release()
    pipeline.stream_handler = VideoStreamHandler(source=req.source, width=800, height=600)
    is_live = not pipeline.stream_handler.is_synthetic
    return {"success": True, "source": req.source, "is_live": is_live}


@app.get("/api/switches")
def get_switches():
    """Returns IoT switch controller status and audit log."""
    return pipeline.switch_controller.get_status()


@app.post("/api/sensor_trigger")
def trigger_sensor(req: SensorTriggerRequest):
    """Handles external PIR motion sensor triggers from Raspberry Pi."""
    if req.zone_id not in pipeline.zone_manager.zones:
        raise HTTPException(status_code=404, detail="Zone not found")
    pipeline.zone_manager.trigger_sensor(req.zone_id, req.motion)
    return {"success": True, "zone_id": req.zone_id, "motion": req.motion}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        while True:
            # Keep alive and listen for client commands
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "scenario":
                    pipeline.switch_scenario(cmd.get("value"))
                elif cmd.get("action") == "sensor_trigger":
                    zone_id = cmd.get("zone_id")
                    motion = cmd.get("motion", True)
                    if zone_id and zone_id in pipeline.zone_manager.zones:
                        pipeline.zone_manager.trigger_sensor(zone_id, motion)
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Frontend dashboard loading...</h1>")
