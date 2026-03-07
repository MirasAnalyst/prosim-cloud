"""Pump performance curves, NPSH calculations, and operating point analysis.

Provides:
  - PumpCurve: head vs flow and efficiency vs flow with quadratic interpolation
  - NPSH available auto-calculation from inlet conditions
  - Operating point determination (pump curve / system curve intersection)
  - Affinity laws for speed changes
"""

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# Try to import thermo for vapor pressure lookup
_thermo_available = False
try:
    from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]
    _thermo_available = True
except ImportError:
    pass

_G = 9.80665  # m/s² — standard gravity


class PumpCurve:
    """Pump characteristic curve: head and efficiency as functions of flow.

    The curve is defined by a set of (flow, head, efficiency) data points.
    Interpolation uses quadratic (numpy polyfit) if available, else piecewise linear.

    Args:
        flow_points: Volumetric flow rates (m³/s)
        head_points: Pump head values (m)
        efficiency_points: Pump efficiency values (0-1 fractional)
        speed_rpm: Pump speed for this curve (rpm)
    """

    def __init__(
        self,
        flow_points: list[float],
        head_points: list[float],
        efficiency_points: list[float],
        speed_rpm: float = 1450.0,
    ):
        if len(flow_points) < 2:
            raise ValueError("Need at least 2 data points for pump curve")
        if len(flow_points) != len(head_points) or len(flow_points) != len(efficiency_points):
            raise ValueError("flow, head, and efficiency arrays must have equal length")

        self.flow_points = list(flow_points)
        self.head_points = list(head_points)
        self.efficiency_points = list(efficiency_points)
        self.speed_rpm = speed_rpm

        # Fit quadratic polynomials: H = a*Q² + b*Q + c
        self._head_coeffs = self._fit_poly(flow_points, head_points)
        self._eta_coeffs = self._fit_poly(flow_points, efficiency_points)

    @staticmethod
    def _fit_poly(x: list[float], y: list[float]) -> tuple[float, float, float]:
        """Fit a quadratic polynomial y = a*x² + b*x + c using least squares."""
        n = len(x)
        if n == 2:
            # Linear fit, no quadratic term
            b = (y[1] - y[0]) / (x[1] - x[0]) if x[1] != x[0] else 0.0
            c = y[0] - b * x[0]
            return (0.0, b, c)

        # Manual least-squares for ax² + bx + c
        try:
            import numpy as np
            coeffs = np.polyfit(x, y, min(2, n - 1))
            if len(coeffs) == 3:
                return (float(coeffs[0]), float(coeffs[1]), float(coeffs[2]))
            elif len(coeffs) == 2:
                return (0.0, float(coeffs[0]), float(coeffs[1]))
            else:
                return (0.0, 0.0, float(coeffs[0]))
        except ImportError:
            # Fallback: use 3-point quadratic fit (first, middle, last)
            if n >= 3:
                i0, i1, i2 = 0, n // 2, n - 1
                x0, x1, x2 = x[i0], x[i1], x[i2]
                y0, y1, y2 = y[i0], y[i1], y[i2]
                denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
                if abs(denom) > 1e-30:
                    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
                    b = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
                    c = (x1 * x2 * (x1 - x2) * y0 + x2 * x0 * (x2 - x0) * y1 + x0 * x1 * (x0 - x1) * y2) / denom
                    return (a, b, c)
            # Linear fallback
            b_val = (y[-1] - y[0]) / (x[-1] - x[0]) if x[-1] != x[0] else 0.0
            c_val = y[0] - b_val * x[0]
            return (0.0, b_val, c_val)

    def head_at_flow(self, Q: float) -> float:
        """Pump head (m) at volumetric flow Q (m³/s)."""
        a, b, c = self._head_coeffs
        return a * Q * Q + b * Q + c

    def efficiency_at_flow(self, Q: float) -> float:
        """Pump efficiency (0-1) at volumetric flow Q (m³/s)."""
        a, b, c = self._eta_coeffs
        eta = a * Q * Q + b * Q + c
        return max(0.01, min(0.95, eta))

    def power_at_flow(self, Q: float, rho: float = 998.0) -> float:
        """Shaft power (W) at volumetric flow Q (m³/s).

        P = rho * g * Q * H / eta
        """
        H = self.head_at_flow(Q)
        eta = self.efficiency_at_flow(Q)
        return rho * _G * Q * max(H, 0) / max(eta, 0.01)

    def at_speed(self, new_speed_rpm: float) -> "PumpCurve":
        """Return a new PumpCurve scaled to a different speed using affinity laws.

        Affinity laws:
            Q₂/Q₁ = N₂/N₁
            H₂/H₁ = (N₂/N₁)²
            P₂/P₁ = (N₂/N₁)³
        """
        ratio = new_speed_rpm / self.speed_rpm if self.speed_rpm > 0 else 1.0
        new_flows = [Q * ratio for Q in self.flow_points]
        new_heads = [H * ratio ** 2 for H in self.head_points]
        # Efficiency approximately constant with speed change
        return PumpCurve(new_flows, new_heads, list(self.efficiency_points), new_speed_rpm)


def calculate_npsh_available(
    P_suction_Pa: float,
    T_K: float,
    fluid: str = "water",
    v_inlet_m_s: float = 0.0,
    z_elevation_m: float = 0.0,
    rho_kg_m3: float | None = None,
) -> dict[str, Any]:
    """Calculate Net Positive Suction Head Available (NPSH_a).

    NPSH_a = (P_suction - P_vapor) / (rho * g) + v²/(2g) + z

    Args:
        P_suction_Pa: Suction pressure (Pa absolute)
        T_K: Fluid temperature (K)
        fluid: Fluid name for vapor pressure lookup
        v_inlet_m_s: Inlet velocity (m/s) for velocity head contribution
        z_elevation_m: Elevation of liquid surface above pump centerline (m)
        rho_kg_m3: Fluid density (kg/m³). Auto-calculated for water if None.

    Returns:
        Dict with NPSH_a (m), P_vapor, velocity_head, components.
    """
    # Get vapor pressure
    P_vapor = None
    if _thermo_available:
        try:
            from app.services.flash_helpers import normalize_compound_name
            fluid_name = normalize_compound_name(fluid)
            _, corr = ChemicalConstantsPackage.from_IDs([fluid_name])
            P_vapor = corr.VaporPressures[0](T_K)
        except Exception:
            pass

    if P_vapor is None:
        # Fallback: Antoine for water
        if fluid.lower() in ("water", "h2o", "steam"):
            if 273.15 <= T_K <= 373.15:
                T_C = T_K - 273.15
                # Antoine constants for water (NIST)
                P_vapor = 10 ** (8.07131 - 1730.63 / (233.426 + T_C)) * 133.322  # mmHg to Pa
            else:
                P_vapor = 101325.0  # fallback
        else:
            return {"status": "error", "error": f"Cannot determine vapor pressure for {fluid}"}

    # Density
    if rho_kg_m3 is None:
        # Water density approximation
        if fluid.lower() in ("water", "h2o", "steam"):
            T_C = T_K - 273.15
            rho_kg_m3 = 1000.0 * (1.0 - 0.0002 * (T_C - 4.0) ** 2 / 100.0)  # rough
            rho_kg_m3 = max(rho_kg_m3, 800.0)
        else:
            rho_kg_m3 = 998.0  # default

    # NPSH_a components
    pressure_head = (P_suction_Pa - P_vapor) / (rho_kg_m3 * _G)
    velocity_head = v_inlet_m_s ** 2 / (2.0 * _G)
    elevation_head = z_elevation_m

    npsh_a = pressure_head + velocity_head + elevation_head

    return {
        "status": "success",
        "NPSH_a_m": round(npsh_a, 4),
        "P_suction_Pa": P_suction_Pa,
        "P_vapor_Pa": round(P_vapor, 2),
        "rho_kg_m3": round(rho_kg_m3, 2),
        "pressure_head_m": round(pressure_head, 4),
        "velocity_head_m": round(velocity_head, 4),
        "elevation_head_m": round(elevation_head, 4),
        "T_K": T_K,
        "fluid": fluid,
    }


def find_operating_point(
    pump_curve: PumpCurve,
    system_curve_coeffs: tuple[float, float],
    rho: float = 998.0,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> dict[str, Any]:
    """Find pump operating point: intersection of pump curve and system curve.

    System curve: H_system = H_static + K_system * Q²
    where H_static is the static head and K_system is the system resistance coefficient.

    Args:
        pump_curve: PumpCurve instance
        system_curve_coeffs: (H_static_m, K_system) where H_sys = H_static + K * Q²
        rho: Fluid density (kg/m³)
        tol: Convergence tolerance on head difference (m)
        max_iter: Maximum iterations

    Returns:
        Dict with Q_operating, H_operating, efficiency, power, converged.
    """
    H_static, K_sys = system_curve_coeffs

    # Bisection on f(Q) = H_pump(Q) - H_system(Q)
    Q_min = 0.0
    Q_max = max(pump_curve.flow_points) * 1.5 if pump_curve.flow_points else 1.0

    def f(Q: float) -> float:
        H_pump = pump_curve.head_at_flow(Q)
        H_sys = H_static + K_sys * Q * Q
        return H_pump - H_sys

    # Check if solution exists
    f_min = f(Q_min)
    f_max = f(Q_max)

    if f_min < 0:
        # Pump can't overcome static head
        return {
            "status": "error",
            "error": "Pump shutoff head is below system static head",
            "converged": False,
        }

    if f_max > 0:
        # Extend search range
        Q_max *= 2.0
        f_max = f(Q_max)

    if f_min * f_max > 0:
        return {
            "status": "error",
            "error": "No intersection found between pump and system curves",
            "converged": False,
        }

    # Bisection
    converged = False
    for _ in range(max_iter):
        Q_mid = (Q_min + Q_max) / 2.0
        f_mid = f(Q_mid)
        if abs(f_mid) < tol:
            converged = True
            break
        if f_mid > 0:
            Q_min = Q_mid
        else:
            Q_max = Q_mid

    Q_op = (Q_min + Q_max) / 2.0
    H_op = pump_curve.head_at_flow(Q_op)
    eta_op = pump_curve.efficiency_at_flow(Q_op)
    power_op = pump_curve.power_at_flow(Q_op, rho)

    return {
        "status": "success",
        "converged": converged,
        "Q_m3_s": round(Q_op, 6),
        "H_m": round(H_op, 4),
        "efficiency": round(eta_op, 4),
        "power_W": round(power_op, 2),
        "power_kW": round(power_op / 1000.0, 4),
    }


def affinity_laws(
    Q1: float, H1: float, P1: float, N1: float, N2: float,
) -> dict[str, float]:
    """Apply affinity laws for speed change.

    Args:
        Q1: Original flow (m³/s)
        H1: Original head (m)
        P1: Original power (W)
        N1: Original speed (rpm)
        N2: New speed (rpm)

    Returns:
        Dict with Q2, H2, P2 at new speed.
    """
    ratio = N2 / N1 if N1 > 0 else 1.0
    return {
        "Q2_m3_s": Q1 * ratio,
        "H2_m": H1 * ratio ** 2,
        "P2_W": P1 * ratio ** 3,
        "speed_ratio": ratio,
    }
