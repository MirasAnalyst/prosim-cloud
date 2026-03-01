# CLAUDE.md

## Project
ProSim Cloud — cloud-based process simulation SaaS (like Aspen HYSYS) with AI co-pilot. Monorepo: `/frontend` (Vite+React+TS, React Flow, Zustand, Tailwind) and `/backend` (FastAPI, SQLAlchemy+psycopg, Supabase PostgreSQL, OpenAI). Backend runs on port 8000, frontend on 5173 with Vite proxy for `/api`.

## Architecture
- **Backend engine**: `backend/app/services/dwsim_engine.py` (~2100 lines) — simulation engine with thermo library integration. Priority: DWSIM (pythonnet) → thermo (PR/SRK/NRTL/UNIQUAC flash) → basic energy/mass balance fallback. Key internals:
  - `_flash_tp()` — shared TP flash helper returning H, S, Cp, VF, rho_liquid, flasher object, MW_mix. Uses `FlashPureVLS` for single-component, `FlashVL` for mixtures.
  - `_normalize_nodes()` — converts React Flow `{type:"equipment", data:{equipmentType}}` to flat `{type:"Heater"}` format.
  - `_build_feed_from_params()` — builds SI feed from user params with thermo flash for real enthalpy.
  - `_get_mw()` — cached molecular weight lookup (thermo + builtin table of 40+ compounds).
  - `_estimate_cp()` — composition-weighted Cp fallback when thermo unavailable.
  - `_get_density()` — flash-based density helper; gas-aware (ideal gas fallback `P*MW/R/T`), liquid uses `rho_liquid`.
  - `_topological_sort()` — returns `(sorted_ids, cycle_ids)` tuple for recycle detection.
  - Per-equipment try/except inside simulation loop — individual failures produce `{"error": str}` without losing other results.
- **Frontend stores**: Zustand stores in `frontend/src/stores/` — `flowsheetStore.ts` (nodes/edges/persistence), `simulationStore.ts` (run sim/results/property package).
- **Unit convention**: Frontend uses °C/kPa/kW/%. Engine uses K/Pa/W/fraction internally. Conversion helpers (`_c_to_k`, `_kpa_to_pa`, `_w_to_kw`) at I/O boundaries in `dwsim_engine.py`.
- **API routes**: `/api/projects`, `/api/projects/{id}/flowsheet`, `/api/simulation/run`, `/api/compounds/search`, `/api/agent/chat`.
- **Schemas**: `backend/app/schemas/flowsheet.py` (NodeData, EdgeData with camelCase aliases), `backend/app/schemas/simulation.py` (SimulationRequest with property_package validation + node/edge limits).
- **E2E tests**: `frontend/e2e/` with Playwright config in `frontend/playwright.config.ts`. 29 tests: 7 Phase 3 accuracy, 3 AI flowsheet, 5 Tier 2, 4 Tier 3, 6 Tier 4, 4 Tier 5. Tests call `/api/simulation/run` in-browser and verify result correctness + UI rendering.

## Current State (Tier 5 Complete)
- 16 equipment types with thermo-integrated calculations (Heater, Cooler, Mixer, Splitter, Separator, Pump, Compressor, Valve, HeatExchanger, DistillationColumn, CSTRReactor, PFRReactor, ConversionReactor, Absorber, Stripper, Cyclone)
- Compound search endpoint with 40+ curated compounds + optional thermo library lookup
- Feed Conditions editor in PropertyInspector (compound search, composition table, auto-normalize)
- Property package selection (Peng-Robinson, SRK, NRTL, UNIQUAC) — dropdown in TopNav, passed through to engine
- Stream labels on canvas edges (T°C | P kPa | flow kg/s) after simulation
- Equipment result badges on nodes (Q kW, W kW, VF) after simulation
- Flowsheet persistence with debounced auto-save (1s) and project load on mount
- Editable project name in TopNav
- Bottom panel shows simulation logs and stream results table with correct units (kg/s)
- **Phase 3 — Engine accuracy overhaul**:
  - Composition-aware enthalpy system (replaced water-Cp with thermo flash H or `_estimate_cp()` fallback)
  - Molar-weighted mixer composition (was mass-averaged — H2+decane z_H2 now 0.986 not 0.50)
  - Single-component flash support via `FlashPureVLS` (pure propane VF=1.0, not fallback 0.1)
  - SRK BIPs match EOS (`"ChemSep SRK"` when SRK selected, not always PR)
  - Entropy-based isentropic compressor (flash at S_in, P_out instead of Cp-R gamma)
  - Valve HP flash for real JT cooling (natural gas drops ~15K, not T_out=T_in)
  - HX uses real Cp per side from thermo flash (not hardcoded 4186 for both)
  - Pump uses real liquid density from flash (not hardcoded 1000 kg/m³)
  - Mixer HP flash for outlet temperature (not h_mix / Cp_water)
  - Quick fixes: 0°C heater outlet accepted, feed param guards removed, flash logs upgraded to warning, xylene CAS fixed to o-xylene (95-47-6)
  - 7 Playwright E2E tests validating all fixes
- **Phase 4 — AI-powered flowsheet generation from text prompts**:
  - OpenAI function calling (tools) with `generate_flowsheet` tool definition (13 equipment types, port IDs, parameter keys)
  - Backend parses tool call → FlowsheetAction, follow-up call for text explanation
  - Frontend `applyFlowsheetAction()`: maps temp IDs → UUIDs, auto-layout (topological sort), merges AI params over defaults
  - Auto-layout: longest-path Kahn's algorithm, left-to-right columns, vertical centering
  - ChatMessage green badge: "Created N equipment with M connections"
  - Equipment type validation, feedComposition stringify, system message filtering
  - `loadFlowsheet()` now triggers `debounceSave()` for persistence
- **Tier 2 — Engine correctness & robustness** (13 items):
  - Per-equipment try/except: one failure no longer loses all results, returns `status: "partial"` with `converged: false`
  - Division-by-zero guards: pump rho≤0, compressor P_in≤0 / P_out<P_in, mf≤0 clamped to 1e-10
  - `_get_density()` helper: flash-based, gas uses `gas.rho_mass()` or ideal gas fallback, liquid uses `rho_liquid`
  - CSTR/PFR use real density — gas-phase methane at 300°C/2000kPa gives rho≈9 kg/m³ (was hardcoded 1000)
  - ConversionReactor applies conversion: reduces key reactant mole fraction by `(1-X)`, adds "products" pseudo-component
  - Heater/Cooler duty-mode: HP flash for real T_out and VF (heating water past 100°C now shows VF>0)
  - `_GAMMA_TABLE` (30 compounds): composition-weighted heat capacity ratio for compressor gamma fallback
  - Pump Cp from flash when available (same pattern as HX)
  - HX hot/cold swap: tracks `swapped` flag, reverses outlet port assignment so `out-hot` always maps to original hot stream
  - Distillation FUG (Fenske-Underwood-Gilliland): K-values from bubble-point flash, proper component split with HK recovery baseline, boiling-point fallback
  - NRTL warning: logs "using Peng-Robinson fallback" when NRTL selected
  - Recycle detection: `_topological_sort` returns cycle_ids, sets `converged: false` + `recycle_detected: true`
  - SimulationRequest validation: `property_package` must be PengRobinson/SRK/NRTL, nodes max 200 with `id`, edges max 500 with `source`/`target`
  - 5 new Playwright E2E tests (15 total: 7 Phase 3 + 3 AI + 5 Tier 2)
- **Tier 4 — Core simulation capabilities** (6 items):
  - UNIQUAC + proper NRTL: `_flash_tp()` builds `GibbsExcessLiquid` with `NRTLModel`/`UNIQUACModel` for activity coefficient models; BIPs from IPDB with zero-matrix fallback; gas stays `CEOSGas(PRMIX)`; uses `UNIFAC_Rs`/`UNIFAC_Qs` for UNIQUAC r/q parameters
  - Tear-stream convergence: outer iteration loop (max 50) with Wegstein acceleration (`q = s/(s-1)`, clamped `[-5, 0.9]`) and damping (0.5); tear edges detected from topological sort back-edges
  - Mass/energy balance validation: post-loop check of `sum(inlet flows) vs sum(outlet flows)` per node; stores `mass_balance_ok`, `energy_balance_ok` in `convergence_info`
  - Unit operation validation: pre-loop topology checks (Mixer ≥2 inlets, HX 2 inlets, Splitter ≥2 outlets) with WARNING logs
  - Absorber & Stripper: Kremser equation `N = ln[(y_in/y_out)(1-1/A)+1/A] / ln(A)` with `A = L/(mG)`; K-values from flash; mass flows computed from component material balance; 4 ports each
  - Chat memory persistence: `ChatMessage` SQLAlchemy model, `GET/POST/DELETE /api/projects/{id}/chat`, frontend load/save in agentStore
  - 6 new Playwright E2E tests (25 total)
- **Tier 5 — Enhancements** (8 items):
  - Equipment sizing: Souders-Brown (separators), `A=Q/(U*LMTD)` (HX), Fair's flooding (columns); `sizing` dict in equipment results
  - Color-coded streams: VF-based stroke color (blue liquid, red gas, orange two-phase)
  - Grid snapping: `snapToGrid snapGrid={[20, 20]}` on ReactFlow
  - Toast notifications: `sonner` library, toasts on sim complete/error and AI flowsheet apply
  - Keyboard shortcuts: `Ctrl+S` save, `Ctrl+Enter` simulate, `Escape` deselect
  - Sortable stream table: click-to-sort headers, CSV export button in BottomPanel
  - Cyclone equipment: Shepherd-Lapple `ΔP = K * ρ * V² / 2`, 2 outlets (gas + solids)
  - Troubleshooting assistant: expert rules in AI system prompt for convergence failures, equipment errors, property package guidance
  - 4 new Playwright E2E tests (29 total)

## Key Lessons

### Phase 1: Frontend↔Backend Data Contract Mismatches
Built full stack in parallel, then chem-soft review caught 14 critical mismatches: equipment type casing, parameter key naming (camelCase vs snake_case), unit systems, data structure access (`node.parameters` vs `node.data`), and engineering errors. Fix: rewrote `dwsim_engine.py` with unit conversion helpers, matched all keys to frontend conventions. **Always cross-check frontend↔backend data contracts before declaring integration complete.**

### Phase 2: Mistakes and Resolutions

1. **React Flow node format mismatch**: Engine read `node.type` expecting "Heater" but got "equipment" (React Flow wraps actual type in `node.data.equipmentType`). All equipment silently skipped. Fix: added `_normalize_nodes()` to extract `data.equipmentType` into flat `type` field.

2. **Edge handle snake_case vs camelCase**: Pydantic `EdgeData` had `source_handle` (snake_case) but frontend sends `sourceHandle` (camelCase). Handles stored as `None`, breaking stream propagation — separator fell back to 10% VF, stream labels empty. Fix: added `Field(alias="sourceHandle")` + `populate_by_name=True` in schema, and `e.sourceHandle ?? e.source_handle` fallback in frontend loader.

3. **thermo `state.liquid0` AttributeError**: When VF=1.0 (all gas), accessing `state.liquid0` crashes instead of returning None. Flash silently failed, falling back to water Cp=4186. Fix: changed to `getattr(state, 'liquid0', None)` and `getattr(state, 'gas', None)`.

4. **Backend agent never started work**: Spawned 3 parallel agents but the chem-soft backend agent stayed idle. Fix: implemented all backend changes directly as team-lead instead of waiting. Lesson: don't block on a stuck agent — take over the work.

### Phase 3: Mistakes and Resolutions

1. **`FlashVL` division-by-zero for single components**: `thermo.FlashVL` crashes on single-component flash (e.g., pure propane). Fix: use `FlashPureVLS(constants, properties, liquids=[liq], gas=gas, solids=[])` when `len(comp_names) == 1`. Always import both flash classes.

2. **Separator default params override inlet conditions**: Separator `params.get("temperature", ...)` returns its *default parameter value* (25°C) even when upstream sends 150°C, because the equipment library populates defaults. Test showed compressor work 914 kW instead of 120 kW. Fix: downstream equipment should not pass default feed params — only user-specified overrides. In E2E tests, omit params for non-feed equipment.

3. **Playwright drag-and-drop fragility**: React Flow canvas drag-and-drop via mouse events is unreliable in headless Chromium. Fix: use API-level simulation calls in-browser (`page.evaluate` + `fetch`) for accuracy tests, reserve UI interaction tests for verifying badge/label rendering on already-loaded flowsheets.

### Phase 4: Mistakes and Resolutions

1. **GPT-4o returned empty parameters**: `additionalProperties: True` with optional field — model skipped it. Fix: made `parameters` required + added few-shot example.

2. **`_normalize_nodes()` read `data.label` not `data.name`**: AI nodes showed UUIDs in sim logs. Fix: `data.get("name", data.get("label", ...))`.

3. **`loadFlowsheet()` missing `debounceSave()`**: AI flowsheets lost on refresh. Fix: added `debounceSave(get)` after `set()`.

4. **`model_dump()` included None fields**: Follow-up OpenAI call could fail from null `refusal`/`audio`. Fix: `model_dump(exclude_none=True)`.

5. **AI couldn't generate CSTR/PFR/DistillationColumn**: GPT-4o returned text instead of tool call for complex equipment. Fix: added few-shot examples (Examples 4–6).

6. **Mixer/HX only received one feed**: Tool schema can't represent two independent feeds. Fix: AI creates Heater pass-throughs as feed sources for each inlet (Examples 2–3).

### Tier 2: Mistakes and Resolutions

1. **FUG K-values all 1.0 for subcooled feed**: Benzene/toluene at 90°C/101kPa is all-liquid (VF=0), so `gas_zs == liq_zs` giving K=1, alpha=1, and FUG silently fell back to boiling-point method. Fix: detect single-phase feeds and flash at bubble point (`VF=0`) to get two-phase K-values.

2. **FUG purity only 66.7% instead of 99%**: Component split formula `d_i/b_i = alpha_i^N_eff` was missing the HK recovery baseline — heavy key splits 50/50 regardless of stages. Fix: use `d_i/b_i = (d_hk/b_hk) * alpha_i^N_eff` with `d_hk/b_hk = 0.01/0.99` for 99% HK recovery in bottoms.

3. **Re-indenting 1025 lines for try/except**: Per-equipment try/except required adding 4 spaces to every line inside the equipment processing loop. Manual Edit calls impractical. Fix: wrote a Python transformation script via Bash that identifies the range, re-indents, and inserts try/except blocks.

### Tier 3: Mistakes and Resolutions

1. **Enthalpy reference state mismatch across equipment**: Pump, Compressor, Valve computed outlet enthalpy as `inlet_h + work/mf`, mixing Cp-fallback and thermo reference frames. Downstream energy balances silently diverged. Fix: compute outlet enthalpy via TP flash at `(T_out, P_out)` for all equipment — same pattern as Heater/Cooler (lines 839-843).

2. **Distillation duty ignored reflux ratio**: `Q_cond = mf * frac_dist * (h_feed - h_dist)` missed the `(R+1)` multiplier and returned 0 when `h_dist == 0` (reference state). Fix: `Q_cond = D*(R+1)*(h_vap_dist - h_dist)` using `_estimate_hvap()`, reboiler from overall energy balance.

3. **HX inlet fallback broken by Python `is` identity check**: `hot = dict(_DEFAULT_FEED)` creates a new object, so `hot is _DEFAULT_FEED` is always `False` — position-based inlet assignment never triggered. Fix: use `None` sentinel instead of `dict()` copy, check `hot is None`.

4. **Compressor flash used wrong variable name after refactor**: Changed `zs_v` (valve's variable) instead of `zs` (compressor's variable) in outlet flash call, causing compressor to crash silently and return no `work` result. Fix: use correct local variable `zs` for each equipment section.

### Tier 4/5: Mistakes and Resolutions

1. **UNIQUAC used Van der Waals volumes instead of UNIFAC r/q parameters**: `UNIQUACModel(rs=constants.Van_der_Waals_volumes, qs=constants.Van_der_Waals_areas)` passed m³/mol values where dimensionless UNIQUAC parameters are expected. Activity coefficients were meaningless but no crash — results silently wrong. Fix: use `constants.UNIFAC_Rs` and `constants.UNIFAC_Qs` (dimensionless) with per-component `None` fallbacks. **Always verify thermo library parameter types match the model's expected units.**

2. **Absorber mass flow hardcoded at 80/20 split**: `mf_out1 = mf1 * 0.8` ignored the Kremser component material balance entirely. The Kremser equation correctly computed compositions but the mass flows were arbitrary. Fix: compute outlet mass flows from actual molar material balance (`sum(moles_c * MW_c)` per outlet), then scale to enforce overall mass balance. **After implementing a thermodynamic model (Kremser), always derive ALL outputs (composition AND flows) from the model — never hardcode mass splits.**

3. **Wegstein acceleration clamped to `[-5, 0]` — no acceleration possible**: Clamping `q` to `max(-5, min(0, q))` only allowed damping (q < 0) or direct substitution (q = 0), never acceleration (0 < q < 1). Recycle loops converged but unnecessarily slowly. Fix: clamp to `[-5, 0.9]` to allow acceleration while avoiding instability near q = 1.

4. **Toast notifications caused Playwright strict mode violations**: Adding `sonner` toasts created duplicate text elements on the page (e.g., "Simulation Complete" appeared in both the bottom panel and a toast). Pre-existing Playwright locators like `page.locator('text=Simulation Complete')` resolved to 2 elements, failing with strict mode error. Fix: add `.first()` to ambiguous locators. **When adding UI notifications (toasts, alerts), check if E2E tests use text-based locators that might match the new elements.**

5. **NRTL test invalidated by proper implementation**: Tier 3 test checked for `WARNING` logs from NRTL's "using Peng-Robinson fallback" message. After T4-1 implemented proper NRTL, there's no fallback and no WARNING. Test silently broke. Fix: updated test to use a Mixer with <2 inlets (triggers T4-4 validation WARNING instead). **When replacing a workaround with a proper implementation, check if tests relied on the workaround's side effects.**

6. **Re-indenting 1100+ lines for tear-stream iteration wrapper**: Wrapping the entire equipment processing loop (lines 858-1959) in an outer `for iteration in range(max_iterations):` required adding 4 spaces to every line. Single Edit call impractical. Fix: wrote Python transformation script to read file, re-indent target range, and write back. Same pattern as Tier 2's try/except re-indent.

### Phase 5 Fix: AI Compound Name Mismatch
GPT-4o guessed compound names from training data (e.g. "CO2", "H2S", "butane") which the engine didn't recognize. Fix: added `### Supported compounds` list (42 exact names from curated list) and rule #7 ("ONLY use compound names from the list") to `SYSTEM_PROMPT` in `openai_agent.py`. AI now outputs "carbon dioxide", "hydrogen sulfide", "n-butane" etc.

## Dev Commands
```bash
# Backend
cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Frontend
cd frontend && npm run dev
# TypeScript check
cd frontend && npx tsc --noEmit
# Python syntax check
python3 -c "import ast; ast.parse(open('file.py').read())"
# Test simulation API
curl -X POST http://localhost:5173/api/simulation/run -H 'Content-Type: application/json' -d '{"nodes":[...],"edges":[...],"property_package":"PengRobinson"}'
# Playwright E2E tests (auto-starts backend + frontend)
cd frontend && npx playwright test
```
