import pytest
import time
from src.models import Zone, Appliance
from src.energy_tracker import EnergyTracker


def test_energy_calculations():
    tracker = EnergyTracker(cost_per_kwh=10.0, co2_kg_per_kwh=0.8)

    # Create dummy zones
    app1 = Appliance(name="Light 1", type="light", wattage=200.0, switch_id="SW1", is_active=True)
    app2 = Appliance(name="Light 2", type="light", wattage=300.0, switch_id="SW2", is_active=False)

    zone = Zone(
        id="test_zone",
        name="Test Bay",
        department="Test",
        camera_polygon=[[0, 0], [1, 0], [1, 1], [0, 1]],
        floor_polygon=[[0, 0], [100, 0], [100, 100], [0, 100]],
        appliances=[app1, app2]
    )

    metrics = tracker.update({"test_zone": zone})
    assert metrics.total_potential_power_w == 500.0
    assert metrics.current_power_draw_w == 200.0
    assert metrics.power_saved_w == 300.0
