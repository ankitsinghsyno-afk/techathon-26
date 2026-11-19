"""
Domain models for Smart Office Energy & Occupancy Management System.
"""
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field
import time


class Appliance(BaseModel):
    name: str
    type: str  # "light", "ac", "socket", "display"
    wattage: float  # Watts (e.g. 240W)
    switch_id: str
    is_active: bool = False


class PersonDetection(BaseModel):
    id: int
    confidence: float
    bbox: List[float] = Field(..., description="[x1, y1, x2, y2] normalized or pixels")
    feet_coord: Tuple[float, float] = Field(..., description="Ground touch point (x, y)")
    zone_id: Optional[str] = None


class Zone(BaseModel):
    id: str
    name: str
    department: str
    camera_polygon: List[List[float]] = Field(..., description="Polygon [[x, y], ...] in camera space (0-1 normalized)")
    floor_polygon: List[List[float]] = Field(..., description="Polygon [[x, y], ...] in 2D floor plan space (pixels)")
    appliances: List[Appliance]
    fixtures: List[Dict[str, Any]] = Field(default_factory=list, description="Physical light and HVAC fixture positions")
    debounce_seconds: float = 8.0
    color: str = "#3B82F6"

    # Runtime state
    current_occupancy: int = 0
    is_occupied: bool = False
    lights_state: bool = False
    ac_state: bool = False
    last_occupied_timestamp: float = 0.0
    time_vacant_seconds: float = 0.0
    time_occupied_seconds: float = 0.0


class EnergyMetrics(BaseModel):
    currency_symbol: str = "₹"
    cost_per_kwh: float = 9.5
    co2_kg_per_kwh: float = 0.82
    total_potential_power_w: float = 0.0  # Power if all zones were ON
    current_power_draw_w: float = 0.0     # Power currently being consumed
    power_saved_w: float = 0.0            # Power saved right now
    cumulative_energy_saved_kwh: float = 0.0
    cumulative_cost_saved: float = 0.0
    cumulative_co2_reduced_kg: float = 0.0


class FloorTelemetry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    floor_name: str
    total_occupancy: int
    zones: Dict[str, Dict[str, Any]]
    detections: List[PersonDetection]
    energy: EnergyMetrics
