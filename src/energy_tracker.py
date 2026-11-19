"""
Energy consumption, cost, and carbon footprint tracking engine.
"""
import time
from typing import Dict, Any, List
from src.models import EnergyMetrics, Zone


class EnergyTracker:
    def __init__(
        self,
        cost_per_kwh: float = 9.5,
        co2_kg_per_kwh: float = 0.82,
        currency_symbol: str = "₹"
    ):
        self.cost_per_kwh = cost_per_kwh
        self.co2_kg_per_kwh = co2_kg_per_kwh
        self.currency_symbol = currency_symbol

        self.last_update_time = time.time()
        self.cumulative_energy_saved_kwh = 0.0
        self.cumulative_energy_consumed_kwh = 0.0
        self.history: List[Dict[str, Any]] = []

    def update(self, zones: Dict[str, Zone]) -> EnergyMetrics:
        now = time.time()
        dt_hours = max(0.0, (now - self.last_update_time) / 3600.0)
        self.last_update_time = now

        total_potential_power_w = 0.0
        current_power_draw_w = 0.0

        for zone in zones.values():
            for app in zone.appliances:
                total_potential_power_w += app.wattage
                if app.is_active:
                    current_power_draw_w += app.wattage

        power_saved_w = max(0.0, total_potential_power_w - current_power_draw_w)

        # Integrate energy
        saved_kwh_delta = (power_saved_w / 1000.0) * dt_hours
        consumed_kwh_delta = (current_power_draw_w / 1000.0) * dt_hours

        self.cumulative_energy_saved_kwh += saved_kwh_delta
        self.cumulative_energy_consumed_kwh += consumed_kwh_delta

        cost_saved = self.cumulative_energy_saved_kwh * self.cost_per_kwh
        co2_reduced = self.cumulative_energy_saved_kwh * self.co2_kg_per_kwh

        metrics = EnergyMetrics(
            currency_symbol=self.currency_symbol,
            cost_per_kwh=self.cost_per_kwh,
            co2_kg_per_kwh=self.co2_kg_per_kwh,
            total_potential_power_w=round(total_potential_power_w, 1),
            current_power_draw_w=round(current_power_draw_w, 1),
            power_saved_w=round(power_saved_w, 1),
            cumulative_energy_saved_kwh=round(self.cumulative_energy_saved_kwh, 4),
            cumulative_cost_saved=round(cost_saved, 2),
            cumulative_co2_reduced_kg=round(co2_reduced, 3)
        )

        # Append to recent history for telemetry graphs (keep last 60 records)
        self.history.append({
            "timestamp": now,
            "power_draw_w": metrics.current_power_draw_w,
            "power_saved_w": metrics.power_saved_w,
            "co2_saved_kg": metrics.cumulative_co2_reduced_kg
        })
        if len(self.history) > 60:
            self.history.pop(0)

        return metrics
