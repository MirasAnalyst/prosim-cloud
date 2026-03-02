"""Pinch analysis engine — Problem Table Algorithm (Linnhoff 1978)."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_pinch_analysis(
    streams: list[dict[str, Any]],
    dt_min: float = 10.0,
) -> dict[str, Any]:
    """Run pinch analysis using Problem Table Algorithm.

    Returns pinch temperature, minimum heating/cooling utilities,
    composite curves, and grand composite curve data.
    """
    if not streams:
        return {"status": "error", "error": "No streams provided"}

    # Classify streams
    hot_streams = []
    cold_streams = []
    for s in streams:
        st = s.get("stream_type", "").lower()
        ts = s["supply_temp"]
        tt = s["target_temp"]
        mcp = s["heat_capacity_flow"]
        name = s.get("name", "")

        if st == "hot" or (not st and ts > tt):
            hot_streams.append({"name": name, "Ts": ts, "Tt": tt, "mCp": mcp})
        else:
            cold_streams.append({"name": name, "Ts": ts, "Tt": tt, "mCp": mcp})

    if not hot_streams and not cold_streams:
        return {"status": "error", "error": "Need at least one hot and one cold stream"}

    # --- Shifted temperatures ---
    # Hot streams: T_shifted = T - ΔTmin/2
    # Cold streams: T_shifted = T + ΔTmin/2
    shift = dt_min / 2.0

    # Collect all shifted temperature levels
    temp_levels = set()
    for h in hot_streams:
        temp_levels.add(h["Ts"] - shift)
        temp_levels.add(h["Tt"] - shift)
    for c in cold_streams:
        temp_levels.add(c["Ts"] + shift)
        temp_levels.add(c["Tt"] + shift)

    temp_levels = sorted(temp_levels, reverse=True)
    if len(temp_levels) < 2:
        return {"status": "error", "error": "Insufficient temperature levels"}

    # --- Problem Table: heat balance per interval ---
    intervals = []
    for i in range(len(temp_levels) - 1):
        t_upper = temp_levels[i]
        t_lower = temp_levels[i + 1]
        dt_interval = t_upper - t_lower

        sum_mcp_hot = sum(h["mCp"] for h in hot_streams
                         if (h["Ts"] - shift) >= t_upper and (h["Tt"] - shift) <= t_lower)
        sum_mcp_cold = sum(c["mCp"] for c in cold_streams
                          if (c["Ts"] + shift) <= t_lower and (c["Tt"] + shift) >= t_upper)

        # Heat surplus = (sum_mCp_hot - sum_mCp_cold) * ΔT
        q_interval = (sum_mcp_hot - sum_mcp_cold) * dt_interval
        intervals.append({
            "t_upper": t_upper,
            "t_lower": t_lower,
            "dt": dt_interval,
            "sum_mcp_hot": sum_mcp_hot,
            "sum_mcp_cold": sum_mcp_cold,
            "q_interval": round(q_interval, 6),
        })

    # --- Heat cascade ---
    # First pass: cascade with Q_H = 0
    cascade = [0.0]
    for iv in intervals:
        cascade.append(cascade[-1] + iv["q_interval"])

    # Q_H_min = max deficit (most negative cascade value)
    min_cascade = min(cascade)
    q_h_min = max(0.0, -min_cascade)

    # Adjusted cascade
    adjusted_cascade = [c + q_h_min for c in cascade]
    q_c_min = adjusted_cascade[-1] if adjusted_cascade else 0.0

    # Pinch: where adjusted cascade = 0
    pinch_temp = None
    for i, val in enumerate(adjusted_cascade):
        if abs(val) < 1e-6:
            pinch_temp = temp_levels[i] if i < len(temp_levels) else None
            break

    # --- Composite curves ---
    hot_composite = _build_composite(hot_streams, is_hot=True)
    cold_composite = _build_composite(cold_streams, is_hot=False)

    # --- Grand composite curve ---
    grand_composite = []
    for i, t in enumerate(temp_levels):
        grand_composite.append({
            "temperature": round(t, 2),
            "enthalpy": round(adjusted_cascade[i], 4),
        })

    # Build heat cascade output
    heat_cascade = []
    for i, iv in enumerate(intervals):
        heat_cascade.append({
            "t_upper": round(iv["t_upper"], 2),
            "t_lower": round(iv["t_lower"], 2),
            "q_interval": round(iv["q_interval"], 4),
            "cascade_in": round(adjusted_cascade[i], 4),
            "cascade_out": round(adjusted_cascade[i + 1], 4),
        })

    return {
        "pinch_temperature": round(pinch_temp, 2) if pinch_temp is not None else None,
        "q_heating_min": round(q_h_min, 4),
        "q_cooling_min": round(q_c_min, 4),
        "hot_composite": hot_composite,
        "cold_composite": cold_composite,
        "grand_composite": grand_composite,
        "heat_cascade": heat_cascade,
        "status": "success",
    }


def _build_composite(streams: list[dict], is_hot: bool) -> list[dict[str, float]]:
    """Build composite curve for hot or cold streams."""
    if not streams:
        return []

    # Collect all temperature levels (actual, not shifted)
    temps = set()
    for s in streams:
        temps.add(s["Ts"])
        temps.add(s["Tt"])
    temps = sorted(temps, reverse=is_hot)

    # Build cumulative enthalpy
    points = []
    cumulative_h = 0.0
    points.append({"temperature": round(temps[0], 2), "enthalpy": 0.0})

    for i in range(len(temps) - 1):
        t1 = temps[i]
        t2 = temps[i + 1]
        dt = abs(t2 - t1)

        # Sum mCp of active streams in this interval
        sum_mcp = 0.0
        for s in streams:
            t_high = max(s["Ts"], s["Tt"])
            t_low = min(s["Ts"], s["Tt"])
            if t_low <= min(t1, t2) and t_high >= max(t1, t2):
                sum_mcp += s["mCp"]

        cumulative_h += sum_mcp * dt
        points.append({"temperature": round(t2, 2), "enthalpy": round(cumulative_h, 4)})

    return points


def extract_streams_from_simulation(sim_results: dict) -> list[dict[str, Any]]:
    """Auto-extract hot/cold streams from heater/cooler duties in simulation results."""
    streams = []
    eq_results = sim_results.get("equipment_results", sim_results.get("results", {}).get("equipment_results", {}))
    stream_results = sim_results.get("stream_results", sim_results.get("results", {}).get("stream_results", {}))

    for eq_id, eq_data in eq_results.items():
        if isinstance(eq_data, str):
            continue
        duty = eq_data.get("duty")
        if duty is None:
            continue

        duty_val = float(duty)
        if abs(duty_val) < 0.01:
            continue

        t_in = eq_data.get("inletTemperature", eq_data.get("inlet_temperature"))
        t_out = eq_data.get("outletTemperature", eq_data.get("outlet_temperature"))
        if t_in is None or t_out is None:
            continue

        t_in_f = float(t_in)
        t_out_f = float(t_out)
        dt = abs(t_out_f - t_in_f)
        if dt < 0.01:
            continue

        mcp = abs(duty_val) / dt
        name = eq_data.get("name", eq_id[:8])

        if duty_val > 0:
            # Heater: cold process stream being heated
            streams.append({
                "name": f"{name} (cold)",
                "supply_temp": t_in_f,
                "target_temp": t_out_f,
                "heat_capacity_flow": round(mcp, 4),
                "stream_type": "cold",
            })
        else:
            # Cooler: hot process stream being cooled
            streams.append({
                "name": f"{name} (hot)",
                "supply_temp": t_in_f,
                "target_temp": t_out_f,
                "heat_capacity_flow": round(mcp, 4),
                "stream_type": "hot",
            })

    return streams
