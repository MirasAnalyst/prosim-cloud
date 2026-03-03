"""Rigorous distillation column solver using the Bubble-Point MESH method.

Implements tray-by-tray distillation simulation with:
  - Thomas algorithm for tridiagonal material balance (M equations)
  - Bubble-point temperature update via Newton-Raphson (E + S equations)
  - Enthalpy balance for flow corrections (H equations)

Stage numbering: 0 = condenser, N-1 = reboiler.

References:
  - Seader, Henley, Roper: "Separation Process Principles" Ch.10
  - Smith: "Design of Equilibrium Stage Processes" (McGraw-Hill)
  - Wang & Henke: "Tridiagonal Matrix for Distillation" (1966)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# thermo library imports (optional — graceful fallback if unavailable)
# ---------------------------------------------------------------------------
_thermo_available = False
try:
    from thermo import (  # type: ignore[import-untyped]
        ChemicalConstantsPackage,
        CEOSGas,
        CEOSLiquid,
        PRMIX,
        FlashVL,
        FlashPureVLS,
    )
    from thermo import GibbsExcessLiquid  # type: ignore[import-untyped]
    from thermo.nrtl import NRTL as NRTLModel  # type: ignore[import-untyped]
    from thermo.uniquac import UNIQUAC as UNIQUACModel  # type: ignore[import-untyped]
    from thermo.interaction_parameters import IPDB  # type: ignore[import-untyped]

    try:
        from thermo import SRKMIX  # type: ignore[import-untyped]
    except ImportError:
        SRKMIX = None  # type: ignore[assignment]

    _thermo_available = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StageData:
    """State variables for a single equilibrium stage (tray or packing section).

    Attributes:
        T: stage temperature [K]
        P: stage pressure [Pa]
        L: liquid molar flow leaving stage [mol/s]
        V: vapor molar flow leaving stage [mol/s]
        x: liquid mole fractions on stage [nc]
        y: vapor mole fractions on stage [nc]
        K: equilibrium K-values at stage conditions [nc]
        H_L: liquid molar enthalpy [J/mol]
        H_V: vapor molar enthalpy [J/mol]
        feed_flow: feed molar flow to this stage [mol/s] (0 if not a feed stage)
        feed_zs: feed composition (mole fractions) if this is a feed stage
        is_feed_stage: whether this stage receives a feed
    """
    T: float = 300.0
    P: float = 101325.0
    L: float = 0.0
    V: float = 0.0
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    K: list[float] = field(default_factory=list)
    H_L: float = 0.0
    H_V: float = 0.0
    feed_flow: float = 0.0
    feed_zs: list[float] = field(default_factory=list)
    is_feed_stage: bool = False


# ---------------------------------------------------------------------------
# Flasher construction (same pattern as phase_envelope.py / dwsim_engine.py)
# ---------------------------------------------------------------------------

def _build_flasher(
    comp_names: list[str],
    property_package: str = "PengRobinson",
) -> tuple[Any, Any, Any, Any, Any] | None:
    """Build phase objects and flasher for the given compounds and property package.

    Returns (gas_template, liq_template, flasher, constants, properties) or None.
    The gas/liq templates are kept so we can rebuild flashers at different T,P
    without re-fetching BIPs every time.
    """
    if not _thermo_available or not comp_names:
        return None

    try:
        constants, properties = ChemicalConstantsPackage.from_IDs(comp_names)
        nc = len(comp_names)
        zs_dummy = [1.0 / nc] * nc  # dummy equimolar for template construction

        T_ref, P_ref = 300.0, 101325.0

        if property_package in ("NRTL", "UNIQUAC") and nc >= 2:
            # Gas phase: PR EOS always
            pr_kijs = [[0.0] * nc for _ in range(nc)]
            try:
                pr_kijs = IPDB.get_ip_asymmetric_matrix("ChemSep PR", constants.CASs, "kij")
            except Exception:
                pass
            eos_kwargs_gas = {
                "Pcs": constants.Pcs, "Tcs": constants.Tcs,
                "omegas": constants.omegas, "kijs": pr_kijs,
            }
            gas = CEOSGas(
                PRMIX, eos_kwargs_gas,
                HeatCapacityGases=properties.HeatCapacityGases,
                T=T_ref, P=P_ref, zs=zs_dummy,
            )

            # Liquid phase: activity coefficient model
            if property_package == "NRTL":
                try:
                    taus = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "bij")
                    alphas = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "alphaij")
                except Exception:
                    taus = [[0.0] * nc for _ in range(nc)]
                    alphas = [[0.3] * nc for _ in range(nc)]
                    logger.warning("NRTL BIPs not found for %s, using zero matrix", comp_names)
                tau_as = None
                try:
                    tau_as = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "aij")
                except Exception:
                    pass
                nrtl_kwargs: dict[str, Any] = {
                    "T": T_ref, "xs": zs_dummy,
                    "tau_bs": taus, "alpha_cs": alphas,
                }
                if tau_as is not None:
                    nrtl_kwargs["tau_as"] = tau_as
                ge_model = NRTLModel(**nrtl_kwargs)
            else:  # UNIQUAC
                try:
                    taus = IPDB.get_ip_asymmetric_matrix("ChemSep UNIQUAC", constants.CASs, "bij")
                except Exception:
                    taus = [[0.0] * nc for _ in range(nc)]
                    logger.warning("UNIQUAC BIPs not found for %s, using zero matrix", comp_names)
                rs = constants.UNIFAC_Rs if constants.UNIFAC_Rs is not None else [2.0] * nc
                qs = constants.UNIFAC_Qs if constants.UNIFAC_Qs is not None else [1.8] * nc
                rs = [r if r is not None else 2.0 for r in rs]
                qs = [q if q is not None else 1.8 for q in qs]
                ge_model = UNIQUACModel(T=T_ref, xs=zs_dummy, tau_bs=taus, rs=rs, qs=qs)

            liq = GibbsExcessLiquid(
                VaporPressures=properties.VaporPressures,
                HeatCapacityGases=properties.HeatCapacityGases,
                VolumeLiquids=properties.VolumeLiquids,
                GibbsExcessModel=ge_model,
                T=T_ref, P=P_ref, zs=zs_dummy,
            )
        else:
            # Cubic EOS (PR or SRK)
            bip_source = "ChemSep SRK" if property_package == "SRK" else "ChemSep PR"
            try:
                kijs = IPDB.get_ip_asymmetric_matrix(bip_source, constants.CASs, "kij")
            except Exception:
                kijs = [[0.0] * nc for _ in range(nc)]

            eos_kwargs = {
                "Pcs": constants.Pcs,
                "Tcs": constants.Tcs,
                "omegas": constants.omegas,
                "kijs": kijs,
            }
            EOS_class = PRMIX
            if property_package == "SRK" and SRKMIX is not None:
                EOS_class = SRKMIX

            gas = CEOSGas(
                EOS_class, eos_kwargs,
                HeatCapacityGases=properties.HeatCapacityGases,
                T=T_ref, P=P_ref, zs=zs_dummy,
            )
            liq = CEOSLiquid(
                EOS_class, eos_kwargs,
                HeatCapacityGases=properties.HeatCapacityGases,
                T=T_ref, P=P_ref, zs=zs_dummy,
            )

        if nc == 1:
            flasher = FlashPureVLS(constants, properties, liquids=[liq], gas=gas, solids=[])
        else:
            flasher = FlashVL(constants, properties, liquid=liq, gas=gas)

        return gas, liq, flasher, constants, properties
    except Exception as exc:
        logger.warning("Failed to build distillation flasher: %s", exc)
        return None


# ---------------------------------------------------------------------------
# K-value and enthalpy helpers
# ---------------------------------------------------------------------------

def _get_k_values(
    flasher: Any,
    T: float,
    P: float,
    x: list[float],
    nc: int,
) -> list[float]:
    """Compute equilibrium K-values at (T, P) for the Bubble-Point MESH method.

    IMPORTANT: For the BP method to work, K-values must be a function of T
    (at given P) that is NOT guaranteed to satisfy sum(K_i * x_i) = 1.
    Otherwise the bubble-point equation f(T) = sum(K_i*x_i) - 1 = 0 is
    trivially satisfied at every T, and the Newton-Raphson update does nothing.

    Strategy:
      1. Attempt a bubble-point flash (VF=0, P, zs=x) to get the equilibrium
         K-values at the *bubble temperature* for composition x. These K-values
         are consistent at T_bubble, not at the given T.
      2. Scale K-values by Wilson temperature dependence to adjust from T_bubble
         to the requested T:
           K_i(T) = K_i(T_bp) * [Wilson_K_i(T) / Wilson_K_i(T_bp)]
      3. Fall back to pure Wilson correlation if bubble-point flash fails.

    This approach gives physically meaningful K(T) that vary with temperature,
    enabling the BP method's convergence mechanism.
    """
    x_norm = _normalize(x)

    # Try bubble-point flash to get reference K-values
    try:
        state_bp = flasher.flash(VF=0.0, P=P, zs=x_norm)
        T_bp = state_bp.T
        gas_bp = getattr(state_bp, 'gas', None)
        liq_bp = getattr(state_bp, 'liquid0', None)

        if gas_bp is not None and liq_bp is not None:
            gas_zs = list(gas_bp.zs)
            liq_zs = list(liq_bp.zs)
            K_bp = []
            for i in range(nc):
                xi = max(liq_zs[i], 1e-15)
                yi = max(gas_zs[i], 1e-15)
                K_bp.append(yi / xi)

            # Scale from T_bubble to requested T using Wilson temperature dependence
            # K_i(T) = K_i(T_bp) * [Wilson(T) / Wilson(T_bp)]
            K_wilson_T = _wilson_k(flasher, T, P, nc)
            K_wilson_Tbp = _wilson_k(flasher, T_bp, P, nc)

            K_scaled = []
            for i in range(nc):
                ratio = K_wilson_T[i] / K_wilson_Tbp[i] if K_wilson_Tbp[i] > 1e-15 else 1.0
                ki = K_bp[i] * ratio
                ki = max(ki, 1e-10)
                ki = min(ki, 1e10)
                K_scaled.append(ki)
            return K_scaled
    except Exception:
        pass

    # Fallback: pure Wilson correlation
    logger.debug("K-value bubble-point flash failed at P=%.0f, using Wilson", P)
    return _wilson_k(flasher, T, P, nc)


def _wilson_k(flasher: Any, T: float, P: float, nc: int) -> list[float]:
    """Wilson correlation for K-values as fallback.

    K_i = (Pc_i / P) * exp(5.37 * (1 + omega_i) * (1 - Tc_i / T))
    """
    constants = flasher.constants if hasattr(flasher, 'constants') else None
    if constants is None:
        return [1.0] * nc

    Tcs = constants.Tcs
    Pcs = constants.Pcs
    omegas = constants.omegas
    K = []
    for i in range(nc):
        try:
            ki = (Pcs[i] / P) * math.exp(5.37 * (1.0 + omegas[i]) * (1.0 - Tcs[i] / T))
            ki = max(ki, 1e-10)
            ki = min(ki, 1e10)
            K.append(ki)
        except (ValueError, ZeroDivisionError, OverflowError):
            K.append(1.0)
    return K


def _get_stage_enthalpies(
    flasher: Any,
    T: float,
    P: float,
    x: list[float],
    y: list[float],
    nc: int,
) -> tuple[float, float]:
    """Compute liquid and vapor molar enthalpies [J/mol] at stage conditions.

    Flashes liquid composition x and vapor composition y at (T, P) to get
    per-phase enthalpies. Falls back to Cp-based estimate on failure.
    """
    H_L = 0.0
    H_V = 0.0

    x_norm = _normalize(x)
    y_norm = _normalize(y)

    # Liquid enthalpy: flash liquid composition at (T, P)
    try:
        state_l = flasher.flash(T=T, P=P, zs=x_norm)
        liq_phase = getattr(state_l, 'liquid0', None)
        if liq_phase is not None:
            H_L = liq_phase.H()
        else:
            # If only gas phase present (superheated), use overall H
            H_L = state_l.H() if callable(getattr(state_l, 'H', None)) else 0.0
    except Exception:
        # Cp-based fallback: H_L ~ Cp_L * (T - T_ref)
        H_L = _cp_fallback_enthalpy(flasher, T, nc, is_liquid=True)

    # Vapor enthalpy: flash vapor composition at (T, P)
    try:
        state_v = flasher.flash(T=T, P=P, zs=y_norm)
        gas_phase = getattr(state_v, 'gas', None)
        if gas_phase is not None:
            H_V = gas_phase.H()
        else:
            H_V = state_v.H() if callable(getattr(state_v, 'H', None)) else 0.0
    except Exception:
        H_V = _cp_fallback_enthalpy(flasher, T, nc, is_liquid=False)

    return H_L, H_V


def _cp_fallback_enthalpy(
    flasher: Any, T: float, nc: int, is_liquid: bool,
) -> float:
    """Simple Cp-based enthalpy estimate relative to 298.15 K reference.

    H = Cp * (T - 298.15)  [J/mol]
    """
    T_ref = 298.15
    # Typical liquid Cp ~ 150 J/mol/K, gas Cp ~ 35 J/mol/K for hydrocarbons
    Cp_default = 150.0 if is_liquid else 35.0
    return Cp_default * (T - T_ref)


def _normalize(x: list[float]) -> list[float]:
    """Normalize a composition vector so it sums to 1.0. Clamp negatives to 0."""
    x_pos = [max(xi, 0.0) for xi in x]
    total = sum(x_pos)
    if total <= 0.0:
        n = len(x_pos)
        return [1.0 / n] * n if n > 0 else []
    return [xi / total for xi in x_pos]


# ---------------------------------------------------------------------------
# Initialization from FUG shortcut results
# ---------------------------------------------------------------------------

def _initialize_stages(
    n_stages: int,
    nc: int,
    feed_stage: int,
    feed_zs: list[float],
    feed_T: float,
    feed_P: float,
    feed_flow: float,
    reflux_ratio: float,
    distillate_rate: float,
    pressure_top: float,
    pressure_bottom: float,
    flasher: Any,
    condenser_type: str,
) -> list[StageData]:
    """Initialize stage profiles using FUG-like estimates.

    - Linear temperature profile between estimated distillate and bottoms T.
    - Constant molal overflow (CMO) for initial L and V flows.
    - Feed composition on all stages as initial guess for x and y.
    - K-values from Wilson correlation at estimated stage conditions.

    Stage 0 = condenser, stage n_stages-1 = reboiler.
    """
    stages: list[StageData] = []

    # Clamp feed_stage to valid range (1 to n_stages-2, between condenser and reboiler)
    feed_stage = max(1, min(feed_stage, n_stages - 2))

    # Linear pressure profile
    P_profile = [
        pressure_top + j * (pressure_bottom - pressure_top) / max(n_stages - 1, 1)
        for j in range(n_stages)
    ]

    # Estimate distillate and bottoms temperatures via bubble-point flashes
    T_dist = feed_T - 20.0  # initial guess
    T_bott = feed_T + 20.0
    try:
        state_bp_top = flasher.flash(VF=0.0, P=pressure_top, zs=_normalize(feed_zs))
        T_dist = state_bp_top.T
    except Exception:
        pass
    try:
        state_bp_bot = flasher.flash(VF=0.0, P=pressure_bottom, zs=_normalize(feed_zs))
        T_bott = state_bp_bot.T + 30.0  # reboiler is hotter than bubble point
    except Exception:
        pass

    # Ensure T_bott > T_dist
    if T_bott <= T_dist:
        T_bott = T_dist + 40.0

    # Linear T profile
    T_profile = [
        T_dist + j * (T_bott - T_dist) / max(n_stages - 1, 1)
        for j in range(n_stages)
    ]

    # CMO initial flows
    # Bottoms rate from overall mass balance: B = F - D
    B = max(feed_flow - distillate_rate, 1e-10)
    D = distillate_rate

    # Rectifying section (above feed): V = L + D, L = R*D
    L_rect = reflux_ratio * D
    V_rect = L_rect + D  # vapor rising in rectifying section

    # Stripping section (below feed): L' = L + q*F, V' = V - (1-q)*F
    # Assume saturated liquid feed (q = 1): L' = L + F, V' = V
    q = 1.0  # assume saturated liquid feed for initialization
    L_strip = L_rect + q * feed_flow
    V_strip = V_rect - (1.0 - q) * feed_flow
    V_strip = max(V_strip, 1e-10)

    zs_init = _normalize(feed_zs)

    for j in range(n_stages):
        sd = StageData()
        sd.T = T_profile[j]
        sd.P = P_profile[j]

        # Flows depend on section
        if j == 0:
            # Condenser
            if condenser_type == "total":
                sd.V = 0.0  # no vapor leaves a total condenser
                sd.L = L_rect
            else:
                # Partial condenser: vapor distillate leaves
                sd.V = D
                sd.L = L_rect
        elif j < feed_stage:
            # Rectifying section
            sd.L = L_rect
            sd.V = V_rect
        elif j == n_stages - 1:
            # Reboiler — L leaving as bottoms product = B = F - D
            B_flow = max(feed_flow - D, 0.01)
            sd.L = B_flow
            sd.V = V_strip
        else:
            # Stripping section (including feed stage)
            sd.L = L_strip
            sd.V = V_strip

        # Initial compositions: use feed composition everywhere
        sd.x = list(zs_init)
        sd.K = _get_k_values(flasher, sd.T, sd.P, sd.x, nc)
        sd.y = _normalize([sd.K[i] * sd.x[i] for i in range(nc)])

        # Initial enthalpies
        sd.H_L, sd.H_V = _get_stage_enthalpies(flasher, sd.T, sd.P, sd.x, sd.y, nc)

        # Feed
        if j == feed_stage:
            sd.is_feed_stage = True
            sd.feed_flow = feed_flow
            sd.feed_zs = list(zs_init)
        else:
            sd.is_feed_stage = False
            sd.feed_flow = 0.0
            sd.feed_zs = [0.0] * nc

        stages.append(sd)

    return stages


# ---------------------------------------------------------------------------
# Thomas algorithm for tridiagonal material balance
# ---------------------------------------------------------------------------

def _thomas_solve(a: list[float], b: list[float], c: list[float], d: list[float]) -> list[float]:
    """Solve tridiagonal system using the Thomas algorithm (TDMA).

    Solves Ax = d where A is tridiagonal with:
      a[j] = sub-diagonal (j=1..n-1; a[0] unused)
      b[j] = diagonal
      c[j] = super-diagonal (j=0..n-2; c[n-1] unused)
      d[j] = right-hand side

    Returns x[0..n-1].
    """
    n = len(b)
    if n == 0:
        return []
    if n == 1:
        return [d[0] / b[0]] if abs(b[0]) > 1e-30 else [0.0]

    # Forward elimination
    c_star = [0.0] * n
    d_star = [0.0] * n

    c_star[0] = c[0] / b[0] if abs(b[0]) > 1e-30 else 0.0
    d_star[0] = d[0] / b[0] if abs(b[0]) > 1e-30 else 0.0

    for j in range(1, n):
        denom = b[j] - a[j] * c_star[j - 1]
        if abs(denom) < 1e-30:
            denom = 1e-30 if denom >= 0 else -1e-30
        c_star[j] = c[j] / denom if j < n - 1 else 0.0
        d_star[j] = (d[j] - a[j] * d_star[j - 1]) / denom

    # Back substitution
    x = [0.0] * n
    x[n - 1] = d_star[n - 1]
    for j in range(n - 2, -1, -1):
        x[j] = d_star[j] - c_star[j] * x[j + 1]

    return x


def _solve_material_balance(
    stages: list[StageData],
    nc: int,
    distillate_rate: float,
    condenser_type: str,
) -> None:
    """Solve the component material balance using the Thomas algorithm.

    Wang-Henke (1966) tridiagonal formulation. For each component i, define
    l_{j,i} = L_j * x_{j,i} (component liquid flow). The stage balance is:

      l_{j-1,i} + V_{j+1}*K_{j+1,i}*l_{j+1,i}/L_{j+1} + f_{j,i}
          = l_{j,i} + V_j*K_{j,i}*l_{j,i}/L_j

    Rearranged as tridiagonal: A_j*l_{j-1} + B_j*l_j + C_j*l_{j+1} = d_j

    Internal stages:
      A_j = 1,  B_j = -(1 + V_j*K_{j,i}/L_j),  C_j = V_{j+1}*K_{j+1,i}/L_{j+1}

    Condenser (j=0, total):  B_0 = -(1 + D/L_0)
    Condenser (j=0, partial): B_0 = -(1 + D*K_{0,i}/L_0)
    Reboiler (j=n-1):        B_{n-1} = -(1 + V_{n-1}*K_{n-1,i}/B)

    After solving for l_{j,i}, update x_{j,i} = l_{j,i} / L_j.
    """
    n = len(stages)
    D = distillate_rate

    for i in range(nc):
        a_vec = [0.0] * n
        b_vec = [0.0] * n
        c_vec = [0.0] * n
        d_vec = [0.0] * n

        B_flow = max(stages[n - 1].L, 1e-10)  # bottoms = reboiler liquid out

        for j in range(n):
            sj = stages[j]
            K_ji = max(sj.K[i], 1e-15)
            f_ji = sj.feed_flow * sj.feed_zs[i] if sj.is_feed_stage and len(sj.feed_zs) > i else 0.0

            if j == 0:
                # Condenser
                L_0 = max(sj.L, 1e-10)
                a_vec[0] = 0.0  # no stage above
                if condenser_type == "total":
                    b_vec[0] = -(1.0 + D / L_0)
                else:
                    b_vec[0] = -(1.0 + D * K_ji / L_0)
                if n > 1:
                    K_1i = max(stages[1].K[i], 1e-15)
                    L_1 = max(stages[1].L, 1e-10)
                    c_vec[0] = stages[1].V * K_1i / L_1
                d_vec[0] = -f_ji

            elif j == n - 1:
                # Reboiler
                a_vec[j] = 1.0
                b_vec[j] = -(1.0 + sj.V * K_ji / B_flow)
                c_vec[j] = 0.0
                d_vec[j] = -f_ji

            else:
                # Internal stage
                L_j = max(sj.L, 1e-10)
                a_vec[j] = 1.0
                b_vec[j] = -(1.0 + sj.V * K_ji / L_j)
                if j < n - 1:
                    sj1 = stages[j + 1]
                    K_j1i = max(sj1.K[i], 1e-15)
                    L_j1 = max(sj1.L, 1e-10)
                    c_vec[j] = sj1.V * K_j1i / L_j1
                d_vec[j] = -f_ji

        # Solve tridiagonal system for l_{j,i}
        l_vals = _thomas_solve(a_vec, b_vec, c_vec, d_vec)

        # Update x_{j,i} from l_{j,i} / L_j
        for j in range(n):
            L_j = max(stages[j].L, 1e-10)
            if j == n - 1:
                L_j = B_flow
            x_ji = l_vals[j] / L_j
            stages[j].x[i] = max(x_ji, 1e-15)

    # Normalize x compositions on each stage
    for j in range(n):
        stages[j].x = _normalize(stages[j].x)


# ---------------------------------------------------------------------------
# Bubble-point temperature update (Newton-Raphson)
# ---------------------------------------------------------------------------

def _update_temperatures(
    stages: list[StageData],
    flasher: Any,
    nc: int,
) -> float:
    """Update stage temperatures using the bubble-point method.

    Two-pronged approach for each stage j:
      1. Primary: Direct bubble-point flash (VF=0, P_j, zs=x_j) to find T_bubble.
         This is the most robust method and avoids the K-value identity problem.
      2. Fallback: Newton-Raphson on f(T) = sum(K_i(T)*x_i) - 1 = 0 using
         Wilson-scaled K-values (which do vary with T).

    After updating T, recompute K-values and y = K*x (normalized) at the new T.

    Returns max|delta_T| across all stages for convergence check.
    """
    max_dT = 0.0

    for j, sj in enumerate(stages):
        x_norm = _normalize(sj.x)
        T_old = sj.T
        P_j = sj.P
        T_new = T_old

        # Primary method: direct bubble-point flash
        bubble_ok = False
        try:
            state_bp = flasher.flash(VF=0.0, P=P_j, zs=x_norm)
            T_bubble = state_bp.T

            # Sanity check: T_bubble should be in a reasonable range
            if 50.0 < T_bubble < 1500.0 and math.isfinite(T_bubble):
                # Damping: limit step to 20 K per iteration for stability
                delta_T = T_bubble - T_old
                delta_T = max(-20.0, min(20.0, delta_T))
                T_new = T_old + delta_T

                # Extract K-values from the bubble-point flash
                gas_bp = getattr(state_bp, 'gas', None)
                liq_bp = getattr(state_bp, 'liquid0', None)
                if gas_bp is not None and liq_bp is not None:
                    gas_zs = list(gas_bp.zs)
                    liq_zs = list(liq_bp.zs)
                    K_new = []
                    for i in range(nc):
                        xi = max(liq_zs[i], 1e-15)
                        yi = max(gas_zs[i], 1e-15)
                        K_new.append(yi / xi)
                    sj.K = K_new
                    bubble_ok = True
        except Exception:
            pass

        if not bubble_ok:
            # Fallback: Newton-Raphson on f(T) = sum(K_i(T)*x_i) - 1
            dT_step = 0.1
            K_at_T = _get_k_values(flasher, T_old, P_j, x_norm, nc)
            f_T = sum(K_at_T[i] * x_norm[i] for i in range(nc)) - 1.0

            if abs(f_T) > 1e-10:
                K_at_T_plus = _get_k_values(flasher, T_old + dT_step, P_j, x_norm, nc)
                f_T_plus = sum(K_at_T_plus[i] * x_norm[i] for i in range(nc)) - 1.0

                f_prime = (f_T_plus - f_T) / dT_step
                if abs(f_prime) > 1e-15:
                    delta_T = -f_T / f_prime
                    delta_T = max(-20.0, min(20.0, delta_T))
                    T_new = T_old + delta_T
                    T_new = max(50.0, min(1500.0, T_new))

            sj.K = _get_k_values(flasher, T_new, P_j, x_norm, nc)

        sj.T = T_new

        # Compute y = K * x, normalized
        sj.y = _normalize([sj.K[i] * x_norm[i] for i in range(nc)])

        max_dT = max(max_dT, abs(T_new - T_old))

    return max_dT


# ---------------------------------------------------------------------------
# Enthalpy balance for flow corrections
# ---------------------------------------------------------------------------

def _update_enthalpies(
    stages: list[StageData],
    flasher: Any,
    nc: int,
) -> None:
    """Recompute liquid and vapor enthalpies at current T, x, y for each stage."""
    for sj in stages:
        sj.H_L, sj.H_V = _get_stage_enthalpies(
            flasher, sj.T, sj.P, sj.x, sj.y, nc,
        )


def _update_flows(
    stages: list[StageData],
    nc: int,
    distillate_rate: float,
    condenser_type: str,
    feed_enthalpy: float | None = None,
) -> None:
    """Update liquid and vapor flows from energy balance corrections.

    Per-stage energy balance (no side draws, Q_j=0 for internal stages):
      V_{j+1}*H_V_{j+1} + L_{j-1}*H_L_{j-1} + F_j*H_F_j
          = V_j*H_V_j + L_j*H_L_j

    Substituting the mass balance V_j = L_{j-1} + V_{j+1} + F_j - L_j and
    solving for L_j:

      L_j = [V_{j+1}*(H_V_{j+1} - H_V_j) + L_{j-1}*(H_L_{j-1} - H_V_j)
             + F_j*(H_F_j - H_V_j)] / (H_L_j - H_V_j)

    Damped 50% to maintain stability. Vapor flows recomputed from mass balance
    in a bottom-up sweep.
    """
    n = len(stages)
    D = distillate_rate

    # Top-down sweep: compute liquid flows from energy balance
    for j in range(n):
        sj = stages[j]
        if j == 0:
            # Condenser: L_0 fixed (reflux ratio specification)
            pass
        elif j == n - 1:
            # Reboiler: L_{n-1} = B from overall balance
            total_feed = sum(s.feed_flow for s in stages)
            sj.L = max(total_feed - D, 1e-10)
        else:
            # Internal stage energy balance
            denom = sj.H_L - sj.H_V
            if abs(denom) < 1.0:
                continue  # H_L ~ H_V; skip to avoid instability

            V_j1 = stages[j + 1].V if j + 1 < n else 0.0
            H_V_j1 = stages[j + 1].H_V if j + 1 < n else 0.0
            L_jm1 = stages[j - 1].L if j > 0 else 0.0
            H_L_jm1 = stages[j - 1].H_L if j > 0 else 0.0

            H_F_j = (feed_enthalpy if feed_enthalpy is not None else (sj.H_L + sj.H_V) / 2.0) if sj.is_feed_stage else 0.0
            F_j = sj.feed_flow

            numerator = (V_j1 * (H_V_j1 - sj.H_V)
                         + L_jm1 * (H_L_jm1 - sj.H_V)
                         + F_j * (H_F_j - sj.H_V))

            L_j_new = numerator / denom
            if L_j_new > 0:
                sj.L = max(0.5 * sj.L + 0.5 * L_j_new, 1e-10)

    # Fix reboiler liquid (bottoms product)
    total_feed = sum(s.feed_flow for s in stages)
    B_flow = max(total_feed - D, 1e-10)
    stages[n - 1].L = B_flow

    # Bottom-up sweep: vapor flows from mass balance
    # Mass balance on stage j: L_{j-1} + V_{j+1} + F_j = L_j + V_j
    # => V_j = L_{j-1} + V_{j+1} + F_j - L_j
    stages[n - 1].V = max(
        stages[n - 2].L + stages[n - 1].feed_flow - B_flow, 1e-10
    )
    for j in range(n - 2, 0, -1):
        sj = stages[j]
        V_j = (stages[j - 1].L + stages[j + 1].V + sj.feed_flow - sj.L)
        sj.V = max(V_j, 1e-10)

    # Condenser vapor balance
    if n >= 2:
        if condenser_type == "total":
            stages[0].V = 0.0
            stages[1].V = max(stages[0].L + D - stages[0].feed_flow, 1e-10)
        else:
            stages[0].V = D
            stages[1].V = max(stages[0].L + D - stages[0].feed_flow, 1e-10)


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_rigorous_distillation(
    feed_comp_names: list[str],
    feed_zs: list[float],
    feed_T: float,
    feed_P: float,
    n_stages: int = 20,
    feed_stage: int = 10,
    reflux_ratio: float = 1.5,
    distillate_rate: float = 0.5,
    feed_flow: float | None = None,
    pressure_top: float = 101325.0,
    pressure_bottom: float | None = None,
    property_package: str = "PengRobinson",
    condenser_type: str = "total",
    tol: float = 1e-6,
    max_iter: int = 100,
) -> dict[str, Any]:
    """Solve a distillation column rigorously using the Bubble-Point MESH method.

    This implements the Wang-Henke (1966) Bubble-Point method:
      1. Initialize from FUG-like estimates (linear T, CMO flows)
      2. Outer loop:
         a. Solve component material balances (Thomas algorithm) -> new x_{j,i}
         b. Bubble-point T update (Newton-Raphson) -> new T_j, K_{j,i}, y_{j,i}
         c. Update enthalpies via TP flash at new T, compositions
         d. Update flows from energy balance corrections
         e. Check convergence: max|delta_T| < tol

    Args:
        feed_comp_names: compound names (thermo library compatible)
        feed_zs: feed mole fractions (will be normalized)
        feed_T: feed temperature [K]
        feed_P: feed pressure [Pa]
        n_stages: total number of equilibrium stages (including condenser and reboiler)
        feed_stage: feed stage index (0-indexed, 0 = condenser, n-1 = reboiler)
        reflux_ratio: external reflux ratio R = L_0 / D
        distillate_rate: distillate molar flow rate [mol/s]
        pressure_top: condenser pressure [Pa]
        pressure_bottom: reboiler pressure [Pa] (defaults to pressure_top + 1000*n_stages Pa)
        property_package: thermodynamic model (PengRobinson, SRK, NRTL, UNIQUAC)
        condenser_type: "total" or "partial"
        tol: temperature convergence tolerance [K]
        max_iter: maximum number of outer iterations

    Returns:
        dict with:
            converged: bool
            iterations: int
            stage_temperatures: list[float] (K)
            stage_compositions: list[dict] (x per stage)
            stage_flows: list[dict] ({L, V} per stage)
            distillate_comp: dict (component: mole fraction)
            bottoms_comp: dict (component: mole fraction)
            condenser_duty: float (W)
            reboiler_duty: float (W)
            condenser_temperature: float (K)
            reboiler_temperature: float (K)
            stage_profiles: list[dict] for visualization
            temperature_history: list[list[float]] (T profile per iteration for diagnostics)
            error: str or None
    """
    nc = len(feed_comp_names)
    result: dict[str, Any] = {
        "converged": False,
        "iterations": 0,
        "stage_temperatures": [],
        "stage_compositions": [],
        "stage_flows": [],
        "distillate_comp": {},
        "bottoms_comp": {},
        "condenser_duty": 0.0,
        "reboiler_duty": 0.0,
        "condenser_temperature": 0.0,
        "reboiler_temperature": 0.0,
        "stage_profiles": [],
        "temperature_history": [],
        "error": None,
    }

    # -----------------------------------------------------------------------
    # Input validation
    # -----------------------------------------------------------------------
    if nc < 2:
        result["error"] = "Rigorous distillation requires at least 2 components"
        return result

    if not _thermo_available:
        result["error"] = "thermo library not available; rigorous distillation requires it"
        return result

    if n_stages < 3:
        result["error"] = "Minimum 3 stages required (condenser + 1 tray + reboiler)"
        return result

    if reflux_ratio <= 0:
        result["error"] = f"Reflux ratio must be positive, got {reflux_ratio}"
        return result

    if distillate_rate <= 0:
        result["error"] = f"Distillate rate must be positive, got {distillate_rate}"
        return result

    # Normalize feed composition
    zs_total = sum(feed_zs)
    if zs_total <= 0:
        result["error"] = "Feed composition sums to zero or negative"
        return result
    feed_zs_norm = [z / zs_total for z in feed_zs]

    # Default bottom pressure: top pressure + ~1 kPa per stage (liquid head)
    if pressure_bottom is None:
        pressure_bottom = pressure_top + n_stages * 1000.0

    condenser_type = condenser_type.lower().strip()
    if condenser_type not in ("total", "partial"):
        condenser_type = "total"

    # Clamp feed stage
    feed_stage = max(1, min(feed_stage, n_stages - 2))

    # -----------------------------------------------------------------------
    # Build flasher
    # -----------------------------------------------------------------------
    flash_result = _build_flasher(feed_comp_names, property_package)
    if flash_result is None:
        result["error"] = f"Failed to build thermodynamic model for {feed_comp_names}"
        return result

    _gas, _liq, flasher, constants, properties = flash_result

    # Feed flow: use caller-supplied value, fallback to D/F=0.5
    if feed_flow is None or feed_flow <= 0:
        feed_flow = max(2.0 * distillate_rate, distillate_rate + 0.1)
    # Ensure B = F - D > 0
    if feed_flow <= distillate_rate:
        feed_flow = distillate_rate * 1.1

    logger.info(
        "Rigorous distillation: %d stages, feed stage %d, R=%.2f, "
        "D=%.4f mol/s, F=%.4f mol/s, %s, condenser=%s",
        n_stages, feed_stage, reflux_ratio, distillate_rate,
        feed_flow, property_package, condenser_type,
    )

    # -----------------------------------------------------------------------
    # Initialize stages
    # -----------------------------------------------------------------------
    try:
        stages = _initialize_stages(
            n_stages=n_stages,
            nc=nc,
            feed_stage=feed_stage,
            feed_zs=feed_zs_norm,
            feed_T=feed_T,
            feed_P=feed_P,
            feed_flow=feed_flow,
            reflux_ratio=reflux_ratio,
            distillate_rate=distillate_rate,
            pressure_top=pressure_top,
            pressure_bottom=pressure_bottom,
            flasher=flasher,
            condenser_type=condenser_type,
        )
    except Exception as exc:
        result["error"] = f"Initialization failed: {exc}"
        logger.warning("Rigorous distillation initialization failed: %s", exc)
        return result

    logger.debug(
        "Initialization complete: T_top=%.1f K, T_bot=%.1f K",
        stages[0].T, stages[-1].T,
    )

    # -----------------------------------------------------------------------
    # Compute actual feed enthalpy for energy balance (not avg of stage H_L/H_V)
    # -----------------------------------------------------------------------
    feed_H: float | None = None
    try:
        state_feed = flasher.flash(T=feed_T, P=feed_P, zs=feed_zs_norm)
        feed_H = state_feed.H()  # J/mol
    except Exception:
        pass  # will fall back to (H_L+H_V)/2 in _update_flows

    # -----------------------------------------------------------------------
    # Outer iteration loop
    # -----------------------------------------------------------------------
    temperature_history: list[list[float]] = []
    converged = False
    iteration = 0
    max_dT: float | None = None

    for iteration in range(1, max_iter + 1):
        # Record current temperature profile
        temperature_history.append([sj.T for sj in stages])

        # Step 1: Solve component material balances (Thomas algorithm)
        try:
            _solve_material_balance(stages, nc, distillate_rate, condenser_type)
        except Exception as exc:
            logger.warning("Material balance solve failed at iteration %d: %s", iteration, exc)
            result["error"] = f"Material balance failed at iteration {iteration}: {exc}"
            break

        # Step 2: Bubble-point temperature update (Newton-Raphson)
        try:
            max_dT = _update_temperatures(stages, flasher, nc)
        except Exception as exc:
            logger.warning("Temperature update failed at iteration %d: %s", iteration, exc)
            result["error"] = f"Temperature update failed at iteration {iteration}: {exc}"
            break

        # Step 3: Update enthalpies at new T, x, y
        try:
            _update_enthalpies(stages, flasher, nc)
        except Exception as exc:
            logger.warning("Enthalpy update failed at iteration %d: %s", iteration, exc)
            # Non-fatal: continue with stale enthalpies

        # Step 4: Update flows from energy balance
        try:
            _update_flows(stages, nc, distillate_rate, condenser_type, feed_enthalpy=feed_H)
        except Exception as exc:
            logger.warning("Flow update failed at iteration %d: %s", iteration, exc)
            # Non-fatal: continue with CMO flows

        # Step 5: Check convergence (require minimum 3 iterations)
        if max_dT is not None and max_dT < tol and iteration >= 3:
            converged = True
            logger.info(
                "Rigorous distillation converged in %d iterations (max|dT|=%.2e K)",
                iteration, max_dT,
            )
            break

        if iteration % 20 == 0:
            logger.debug(
                "Iteration %d: max|dT|=%.4f K, T_top=%.1f K, T_bot=%.1f K",
                iteration, max_dT, stages[0].T, stages[-1].T,
            )

    if not converged and result["error"] is None:
        logger.warning(
            "Rigorous distillation did not converge in %d iterations (max|dT|=%.4f K)",
            max_iter, max_dT if max_dT is not None else float('inf'),
        )

    # -----------------------------------------------------------------------
    # Extract results
    # -----------------------------------------------------------------------
    # Condenser duty (W): Q_c < 0 (heat removed)
    # Energy balance on condenser: V_1*H_V_1 + Q_c = (L_0 + D)*H_L_0  (total)
    # => Q_c = (L_0 + D)*H_L_0 - V_1*H_V_1  (negative since condensing)
    Q_c = 0.0
    if n_stages >= 2:
        V_1 = stages[1].V
        H_V_1 = stages[1].H_V
        if condenser_type == "total":
            Q_c = (stages[0].L + distillate_rate) * stages[0].H_L - V_1 * H_V_1
        else:
            Q_c = stages[0].L * stages[0].H_L + distillate_rate * stages[0].H_V - V_1 * H_V_1
    # Q_c should be negative (heat removed); enforce sign
    if Q_c > 0:
        Q_c = -Q_c

    # Reboiler duty (W): Q_r > 0 (heat added)
    # Overall energy balance: F*H_F + Q_r + Q_c = D*H_D + B*H_B
    # => Q_r = D*H_D + B*H_B - Q_c - F*H_F
    H_F = 0.0
    try:
        state_feed = flasher.flash(T=feed_T, P=feed_P, zs=feed_zs_norm)
        H_F = state_feed.H() if callable(getattr(state_feed, 'H', None)) else 0.0
    except Exception:
        pass

    H_D = stages[0].H_L if condenser_type == "total" else stages[0].H_V
    B_flow = max(feed_flow - distillate_rate, 1e-10)
    H_B = stages[-1].H_L

    Q_r = distillate_rate * H_D + B_flow * H_B - Q_c - feed_flow * H_F
    # Reboiler must add heat
    if Q_r < 0:
        logger.debug("Q_reb=%.1f W (negative from reference state); taking absolute value", Q_r)
        Q_r = abs(Q_r)

    # Distillate and bottoms compositions
    dist_comp = {feed_comp_names[i]: round(stages[0].x[i], 6) for i in range(nc)}
    bott_comp = {feed_comp_names[i]: round(stages[-1].x[i], 6) for i in range(nc)}

    # Build stage profiles for visualization
    stage_profiles = []
    for j, sj in enumerate(stages):
        profile = {
            "stage": j,
            "T_K": round(sj.T, 2),
            "T_C": round(sj.T - 273.15, 2),
            "P_Pa": round(sj.P, 1),
            "P_kPa": round(sj.P / 1000.0, 3),
            "L": round(sj.L, 6),
            "V": round(sj.V, 6),
            "x": {feed_comp_names[i]: round(sj.x[i], 6) for i in range(nc)},
            "y": {feed_comp_names[i]: round(sj.y[i], 6) for i in range(nc)},
            "K": {feed_comp_names[i]: round(sj.K[i], 4) for i in range(nc)},
            "H_L": round(sj.H_L, 2),
            "H_V": round(sj.H_V, 2),
        }
        if sj.is_feed_stage:
            profile["is_feed_stage"] = True
        stage_profiles.append(profile)

    result["converged"] = converged
    result["iterations"] = iteration
    result["stage_temperatures"] = [round(sj.T, 2) for sj in stages]
    result["stage_compositions"] = [
        {feed_comp_names[i]: round(sj.x[i], 6) for i in range(nc)}
        for sj in stages
    ]
    result["stage_flows"] = [
        {"L": round(sj.L, 6), "V": round(sj.V, 6)}
        for sj in stages
    ]
    result["distillate_comp"] = dist_comp
    result["bottoms_comp"] = bott_comp
    result["condenser_duty"] = round(Q_c, 2)
    result["reboiler_duty"] = round(Q_r, 2)
    result["condenser_temperature"] = round(stages[0].T, 2)
    result["reboiler_temperature"] = round(stages[-1].T, 2)
    result["stage_profiles"] = stage_profiles
    result["temperature_history"] = [
        [round(t, 2) for t in temps] for temps in temperature_history
    ]

    # Summary log
    lk_name = feed_comp_names[0] if nc > 0 else "?"
    logger.info(
        "Rigorous distillation result: converged=%s, iter=%d, "
        "T_cond=%.1f C, T_reb=%.1f C, Q_c=%.1f W, Q_r=%.1f W, "
        "distillate %s=%.3f, bottoms %s=%.3f",
        converged, iteration,
        stages[0].T - 273.15, stages[-1].T - 273.15,
        Q_c, Q_r,
        lk_name, dist_comp.get(lk_name, 0),
        feed_comp_names[-1] if nc > 1 else "?",
        bott_comp.get(feed_comp_names[-1], 0) if nc > 1 else 0,
    )

    return result
