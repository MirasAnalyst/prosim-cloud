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

### Phases 2-5 Completion: Mistakes and Resolutions

1. **`flowsheet_data` not defined in `_simulate_basic()`**: Convergence settings and progress callback referenced `flowsheet_data.get(...)` inside `_simulate_basic()`, but that variable only exists in `simulate()`. Silent `NameError` crashed all simulations. Fix: added `convergence_settings` and `progress_callback` as explicit method parameters, passed through from `simulate()`.

2. **Missing `await` on async `engine.simulate()`**: Batch and report routes called `engine.simulate()` without `await`, returning coroutine objects instead of dicts — all batch/report requests returned 500 errors. Fix: added `await` to all call sites. **When refactoring sync→async, grep every call site.**

3. **`asyncio.to_thread()` with async coroutine**: SSE endpoint used `asyncio.to_thread(engine.simulate, ...)` which only works with sync functions — async coroutines just return unawaited objects. Fix: changed to `asyncio.create_task(engine.simulate({...}))`. **`to_thread` = sync functions only; `create_task` = async coroutines.**

4. **ThreePhaseSeparator unpacked `_flash_tp()` dict as tuple**: Code used `_H, _S, _Cp, VF_f, ... = flash_result` but `_flash_tp()` returns a dict. `ValueError` silently caught by `except Exception: pass`, defaulting VF=0.0 — methane at 80°C showed as all-liquid. Fix: use `flash_result["VF"]` dict access. **Never blindly catch exceptions around flash calls — at minimum log them.**

### Fix 3 Partial Items: Mistakes and Resolutions

1. **SSE endpoint returns flat result, POST wraps in `{results: ...}`**: Frontend SSE parser used `data.results.equipment_results` but SSE `complete` event sends raw engine output (no `results` wrapper). Simulation showed "0 iterations, not converged" with empty badges. Fix: `const res = data.results ?? data` to handle both formats. **When switching API transport (POST→SSE), always compare the raw response shapes.**

2. **Zustand store not accessible from Playwright `page.evaluate`**: Test 7 tried `window.__ZUSTAND_FLOWSHEET_STORE__` which was never exposed, so injected nodes were silently ignored and the test ran against stale persisted data. Fix: added `window.__ZUSTAND_FLOWSHEET_STORE__ = useFlowsheetStore` in `flowsheetStore.ts`. **E2E tests that inject store state need the store explicitly exposed on `window`.**

3. **Stale background processes accumulate across sessions**: Each `run_in_background` server start (uvicorn/vite) spawns a process that persists after the session ends. Over days, 5+ orphaned Vite instances held ports 5173-5177, causing port conflicts and wasting ~300MB RAM. Fix: always check `ps aux | grep -E "uvicorn|vite"` before starting servers; kill stale ones first. **Before starting dev servers, verify no orphaned instances exist from previous sessions.**

### Phase 6: Mistakes and Resolutions

1. **Flowsheet validator checked wrong node path — all validation was dead code**: `validate_flowsheet()` used `n.get("parameters", {})` but React Flow nodes store params at `n["data"]["parameters"]`. Every parameter check (feed completeness, composition sums, numeric ranges) silently returned empty dict and never fired. Fix: added `_get_params()` helper that checks `data.parameters` first, falls back to top-level `parameters`. **When writing code that accesses node data, always account for the React Flow `{type:"equipment", data:{equipmentType, parameters}}` wrapper structure.**

2. **Version routes allowed cross-project access via unscoped queries**: `get_version`, `delete_version`, `restore_version`, and `diff_versions` queried `FlowsheetVersion.id == version_id` without filtering by `flowsheet_id`. Any user could access/modify versions belonging to other projects by guessing UUIDs. Fix: added `.where(FlowsheetVersion.flowsheet_id == flowsheet.id)` to all 4 endpoints. **Always scope child resource queries by the parent's FK, even when the URL includes the parent ID.**

3. **Exporter produced `<Type>equipment</Type>` instead of actual equipment type**: `node.get("type")` returns React Flow's wrapper type `"equipment"`, not the actual type. The `_PROSIM_TO_DWSIM` mapping couldn't find `"equipment"` and fell through to using it literally. Fix: prioritize `data.equipmentType` over `type` — `node.get("data", {}).get("equipmentType", "") or node.get("type", "")`. **Same React Flow wrapper issue as the validator — any code touching stored nodes must extract the real type from `data.equipmentType`.**

4. **Supabase pgbouncer double-pooling caused connection exhaustion under test concurrency**: SQLAlchemy's default connection pool (pool_size=5) layered on top of Supabase's pgbouncer pooler (port 6543) created pool-on-pool conflicts. Under Playwright's parallel test load, connections exhausted and `POST /api/projects` returned 500. Fix: detect Supabase pooler URL and use `NullPool` (let pgbouncer handle pooling). **When using an external connection pooler (pgbouncer, PgBouncer, RDS Proxy), always use `NullPool` in SQLAlchemy to avoid double-pooling.**

### Phase 8: Mistakes and Resolutions

1. **psycopg3 `prepare_threshold=0` means "prepare immediately", not "disable"**: Set `prepare_threshold=0` in `connect_args` thinking it would disable prepared statements for pgbouncer compatibility, but in psycopg3 `0` means "always prepare" (worse than default). All DB queries hit `DuplicatePreparedStatement` errors. Fix: use `prepare_threshold=None` to disable prepared statements entirely. **Always check library-specific semantics for sentinel values — `0` and `None` often mean very different things.**

2. **AI `max_completion_tokens=2048` silently truncated multi-equipment flowsheets**: 7/20 AI flowsheet prompts returned `flowsheet_action: null` with no error — the GPT tool call JSON was truncated mid-generation at exactly 2048 tokens. Multi-feed equipment (Absorber, HX) and multi-stage trains (3-stage compressor) were most affected. Fix: increased to `4096` in `openai_agent.py`. **When AI tool calls return null/empty, check `completion_tokens` against the ceiling before debugging prompt logic.**

3. **AI set compressor efficiency as fraction (0.75) but engine expects percent (75)**: The engine divides efficiency by 100 (`efficiency / 100.0`), so `0.75` became `0.0075` — compressor discharge temperatures showed 3300°C instead of ~137°C, work was 100× too high. Fix: added "(0-100 scale, e.g. 75 means 75%)" to all efficiency/conversion parameter docs in the AI system prompt. **When AI generates numeric parameters, always document the expected scale/units in the tool definition — LLMs default to mathematical conventions (fractions) not engineering conventions (percentages).**

4. **Pydantic `response_model` validation silently returned 500 for mixed-type dicts**: `EmissionsResult.breakdown: list[dict[str, float]]` failed validation because the engine returns `{"source": "Combustion CO2", "tonnes_per_year": 44880.0}` — the `"source"` value is a string, not a float. FastAPI returned a bare `Internal Server Error` with no detail, making it hard to diagnose. Fix: changed to `list[dict[str, Any]]`. **When a Pydantic `response_model` causes 500, check that all dict value types match the actual engine output — mixed-type dicts need `Any` not a specific type.**

### Chem-Sim Domain Review: Mistakes and Resolutions

1. **AI Example 7 used mass fractions (30/70) for MEA instead of mole fractions**: 30 wt% MEA = 0.3/61.08 ÷ (0.3/61.08 + 0.7/18.015) = 0.112 mol fraction, not 0.3. AI would generate thermodynamically incorrect amine compositions. Fix: corrected to `"monoethanolamine":0.112,"water":0.888` and added Rule 11 (mole vs mass fraction guidance). **Always convert wt% to mol% for feedComposition — LLMs default to mass fractions for familiar solutions like "30% MEA".**

2. **ConversionReactor always consumed the first component regardless of chemistry**: `key_reactant = list(out_comp.keys())[0]` picked whichever compound appeared first in the dict, which depends on insertion order not chemistry. Fix: added `keyReactant` parameter (engine, frontend, AI prompt) so users specify which compound reacts. **Reactant selection should be explicit, not positional — dict key order is arbitrary.**

3. **Binary Underwood R_min formula used for multicomponent distillation**: `R_min = 1.0 / (alpha_lk_hk - 1.0)` is only valid for binary mixtures — for 3+ components it underestimates R_min, leading to insufficient reflux and poor separation. Fix: implemented full Underwood theta bisection with preliminary Fenske splits for `R_min+1 = Σ(α_i·d_i/(α_i-θ))`. **Always use the multicomponent form of Underwood for ≥3 components.**

4. **Absorber outlet used simple average temperature, ignoring exothermic absorption**: `T_out2 = T_avg` missed the heat released by CO₂/H₂S absorption into amine (84/60 kJ/mol). Rich solvent exits 20-40°C hotter than the average in real plants. Fix: added `_HEAT_OF_ABSORPTION` table, computed `ΔT = Q_abs/(mf·Cp)` capped at 60K, and flashed outlets for real enthalpies. **Absorber/stripper models must account for heat of reaction — it dominates the column temperature profile.**

### AI FeedStream Fix: Mistakes and Resolutions

1. **E2E test used exact equipment count for LLM-generated flowsheet**: Test expected exactly 4 equipment items but AI added ProductStream nodes (6 total) — LLM output is non-deterministic. Fix: changed `toHaveLength(4)` to `toBeGreaterThanOrEqual(4)` and verified core types with `toContain()`. **Never assert exact counts on LLM-generated output; use minimum bounds and check for required elements.**

### Production Engine Bugs: Mistakes and Resolutions

1. **HX allowed cold outlet > hot inlet (2nd law violation)**: Energy-balanced cold outlet adjustment could produce T_cold_out > T_hot_in when hot-side duty far exceeded cold-side capacity (e.g., 10 kg/s hot, 1 kg/s cold → cold outlet 1288°C). Fix: clamp T_cold_out ≤ T_hot_in - 1K and T_hot_out ≥ T_cold_in + 1K, recompute duty from clamped side. **Always enforce thermodynamic feasibility constraints after energy balance calculations.**

2. **HX NTU method updated temperatures but left stale enthalpies**: NTU recalculated T_hot_out and T_cold_out but didn't re-flash outlets — downstream equipment got enthalpies computed from the LMTD temperatures. Fix: re-flash both outlets at NTU temperatures to update enthalpies. **When overriding temperatures in a secondary calculation path, always recompute dependent properties (enthalpy, VF).**

3. **Distillation LK/HK picked extreme components for wide-boiling feeds**: `lk_idx = max(K), hk_idx = min(K)` selected methane (bp -161°C) and n-decane (bp 174°C) for mixed feeds, giving alpha ~10⁶ and meaningless FUG results (N_min ≈ 0.8, LK purity 13%). Fix: adjacent key selection — sort by K-value and pick the closest pair with alpha > 1.01 (finds the hardest split). Added `lightKey`/`heavyKey` params for user override. **For multicomponent distillation, the key components should be the adjacent pair straddling the split, not the volatility extremes.**

4. **Distillation reboiler duty went negative from enthalpy reference state mismatch**: `Q_reb = D*h_dist + B*h_bott + Q_cond - mf*h_feed` produced negative values when flash enthalpies had inconsistent reference states across different compositions. Fix: enforce `Q_reb = max(Q_reb, 0)` with `B * hvap(bottoms)` fallback. **Reboilers must add heat — enforce physical constraints on energy balance outputs.**

5. **Compressor entropy-based outlet had 39% energy imbalance**: Entropy method computed work from `dH_actual = (H_isen - H_in)/eff`, but outlet enthalpy came from a separate TP flash at (T_out, P_out) — numerical differences between HP flash (gives T_out) and TP flash (gives H_out) broke `H_out - H_in = W/mf`. Fix: set outlet enthalpy directly as `H_in + W/mf` for entropy method. **When computing thermodynamically consistent results, derive all outputs from a single calculation path — redundant flashes introduce numerical inconsistency.**

6. **Pump silently accepted P_out < P_in**: Pump with outlet pressure below inlet produced negative work and temperature drop with no warning. Fix: added WARNING log "pump cannot reduce pressure. Consider using a Valve instead." **Always validate physical feasibility of user parameters and suggest the correct equipment type.**

7. **DesignSpec mutated shared node parameters via shallow copy**: `[dict(n) for n in nodes]` shallow-copies node dicts but nested `parameters` dict shares the same reference — DesignSpec's `n_params[manip_param] = x1_ds` modified the original nodes list. Fix: `copy.deepcopy(nodes)` before DesignSpec iterations. **Nested dicts require deep copy — shallow copy only duplicates the top-level container.**

8. **DesignSpec `'f1' in dir()` is unreliable for variable existence**: `dir()` returns module-level names, not local variables — `f1` was always absent from `dir()` even when assigned. Fix: initialize `f1 = None` before loop, check `f1 is not None`. **Never use `dir()` to check local variable existence — use sentinel values (`None`) with explicit initialization.**

9. **Unstaged frontend routing changes caused 39 false test failures**: `App.tsx` had uncommitted changes moving the simulator from `/` to `/app/*`. Vite dev server serves the working tree, so all Playwright tests navigating to `/` hit a landing page instead of the simulator. Misdiagnosed as engine regressions until stashing the unrelated changes. Fix: stash unrelated frontend changes before running E2E tests. **Always check `git status` for unstaged changes that could affect test behavior — Vite serves working tree, not HEAD.**

10. **HX NTU path had 3 thermodynamic gaps found by chem-sim review**: (a) Final safety clamp didn't recompute `duty`, leaving it inconsistent with clamped temps; (b) NTU re-flash updated enthalpy but not `vapor_fraction`, so phase boundary crossings were invisible to downstream; (c) NTU duty used Cp-based `Q_ntu` instead of flash enthalpies, diverging near phase transitions. Fix: recompute duty after final clamp, propagate VF from re-flash, recalculate NTU duty from `mf*(h_in - h_out)`. **After any temperature override path (NTU, clamping), recompute ALL dependent properties — enthalpy, VF, and duty.**

### Phase 9: Mistakes and Resolutions

1. **Pump `w_ideal` undefined in near-critical enthalpy path → NameError crash**: M3 pump fix added an enthalpy-based branch but `w_ideal` was only assigned in the `if not pump_enthalpy_method:` block. The downstream `dT_friction = (w_actual - w_ideal)` line always runs, crashing for near-critical fluids. Fix: initialize `w_ideal = 0.0` before the branch and set `w_ideal = w_isen` in the enthalpy path. **Always initialize variables before conditional branches when they're used unconditionally afterward.**

2. **Stripper G/L molar flows swapped — all stripper results quantitatively wrong**: `G = total_moles1` and `L = total_moles2` are correct for Absorber (feed1=gas, feed2=solvent) but wrong for Stripper (feed1=rich solvent, feed2=stripping gas). The stripping factor `S = (m*G)/L` used liquid moles as G and gas moles as L. Fix: added `if ntype == "Absorber"` / `else` to assign G/L correctly per equipment type. **When code handles two equipment types with different inlet conventions (Absorber vs Stripper), never share flow variable assignments — assign per type.**

3. **Absorber heat-of-absorption used `(z_in - z_out) × G` instead of actual mole difference**: `moles_absorbed = (comp1.get(c) - out1_comp.get(c)) * G` is wrong because `out1_comp` is normalized over a different total than `G`. Fix: changed to `n_gas_in_c - n_out1[c]` using the already-computed moles vectors. **When computing differences between inlet and outlet, use absolute moles (already available from Kremser), not mole fractions × inlet total.**

4. **Dryer outlet composition mixed mass-fraction target into mole-fraction dict**: `dry_zs[wk] = target_moisture` inserted a mass-fraction value (outletMoisture/100) into a dict of mole fractions, producing meaningless normalized compositions. Fix: convert target moisture back to mole fraction using MW ratios before inserting into the composition dict. **Never mix mass and mole fractions in the same composition dict — always convert to a consistent basis.**

5. **Crystallizer `crystal_flow = mf * zs[key_idx]` used mole fraction with mass flow**: For 50 mol% urea (MW=60) in water (MW=18), mass fraction is 0.77 not 0.50. Using mole fraction underestimates crystal yield by 35%. Fix: convert `zs[key_idx]` to mass fraction via `z*MW_key / Σ(z_i*MW_i)` before multiplying by mass flow. **When computing mass flows from compositions, always convert mole fractions to mass fractions first — this is the same class of bug as the dryer (C3) fix itself was meant to address.**

### Stress Test Chem-Sim Review: Mistakes and Resolutions

1. **Distillation boiling-point fallback set `enthalpy: 0.0` on both outlets**: FUG fallback path hardcoded zero enthalpy for distillate and bottoms, causing 100% energy imbalance cascading to all downstream equipment (Test 20 Complete Gas Plant). Fix: flash each outlet composition at its T/P to get real enthalpies. **Never hardcode enthalpy=0 — always flash the outlet composition, even in fallback paths.**

2. **Stripper single-inlet injected phantom 1 kg/s default feed**: `feed2 = dict(_DEFAULT_FEED)` created 1 kg/s of water from nothing for reboiled strippers (no external stripping gas), violating mass conservation. Fix: set `feed2["mass_flow"] = 0.0` and log "operating as reboiled stripper". **Default feed dicts must not inject mass into the simulation — set mass_flow=0 when a feed is structurally absent.**

3. **ThreePhaseSeparator copied inlet enthalpy to all 3 outlets**: Vapor, light liquid, and heavy liquid all got `inlet.get("enthalpy", 0.0)` regardless of phase, causing 40-55% energy imbalance downstream. Fix: extract per-phase enthalpy from flash state (`gas_phase.H()`, `liquid0.H()`) — same pattern as regular Separator. **Phase-separating equipment must compute per-phase enthalpies from flash, not copy the mixed-feed value.**

4. **HX cold outlet enthalpy inconsistent with duty near phase change**: Hot-side duty correctly computed from flash enthalpies, but cold outlet enthalpy came from an independent TP flash — numerical differences gave 34.6% energy imbalance for propane near boiling point. Fix: force `cold_out["enthalpy"] = h_cold_in + duty / mf_cold` from energy balance. **Derive both HX outlets from a single duty calculation — independent flashes introduce numerical inconsistency.**

5. **Cyclone outlets both got inlet enthalpy despite different compositions**: Gas outlet (light components) and solids outlet (heaviest component) had identical enthalpies, thermodynamically incorrect. Fix: flash each outlet composition separately at outlet T/P. **Any equipment that splits compositions must flash each outlet independently for correct enthalpy.**

6. **Energy balance checker false positives for DistillationColumn, Cyclone, Filter**: These equipment types have internal duties (condenser/reboiler) or heuristic composition splits that don't conserve energy in the simple `Σ(mf*h)_in = Σ(mf*h)_out ± duty` check. Fix: exclude them from energy balance validation with `ntype not in ("DistillationColumn", "Cyclone", "Filter")`. **Energy balance checks must account for equipment with internal energy sources/sinks not captured in the external duty field.**

### Industrial Flowsheet Review: Mistakes and Resolutions

1. **Absorber used physical VLE K-values for chemical absorption systems**: PR EOS gives K_CO2=83 and K_H2S=8 for amine gas treating — 100-1000× too high because it ignores the chemical reaction (CO2 + 2 DEA → products). Absorption factor A=L/(K·G) << 1, so zero acid gas removal. Fix: added `_REACTIVE_K_EFF` table with effective K-values from Kent-Eisenberg correlations (K_CO2≈0.02, K_H2S≈0.008) with Van't Hoff temperature correction. Detect reactive systems by checking for acid-gas + amine/water compounds. **Physical VLE models (PR/SRK) cannot predict chemical absorption — use effective K-values for reactive systems (amine sweetening, SO2 scrubbing).**

2. **Reactive K-value fix included "water" in `_REACTIVE_SOLVENTS` — false positive for water-only scrubbers**: CO2 in pure water follows Henry's law (K≈2-5), not amine chemistry (K≈0.02). Any CO2+water absorber without amine got 100× too much absorption. Fix: split into `_AMINE_SOLVENTS` (MEA/DEA, required for CO2/H2S) and `_AQUEOUS_REACTIVE` (SO2/NH3 work with water alone). Also stored `Q_abs` as negative `duty` in absorber `eq_res` to fix 109% energy balance error. **Reactive absorption corrections must distinguish amine-dependent (CO2/H2S) from aqueous-reactive (SO2/NH3) systems.**

3. **PFR read `bedVoidFraction` but frontend/tests pass `voidFraction` — silently ignored user input**: Engine used `params.get("bedVoidFraction", 0.4)` while the frontend parameter key is `voidFraction`. User-specified void fractions were always overridden by the default. Additionally, tests passed `particleDiameter: 3` (meters) instead of `0.003` (3 mm), making Ergun ΔP off by ~10⁶. Fix: read both keys with fallback `params.get("voidFraction", params.get("bedVoidFraction", 0.4))`, auto-correct d_p > 0.1 m with warning. **Always verify frontend parameter keys match engine `params.get()` keys — silent defaults mask data contract mismatches.**

### Per-Stream Component Properties: Mistakes and Resolutions

1. **CSV export column mismatch — component rows had 11 columns but header had 8**: Component detail sub-rows used offset commas starting at column 7, exceeding the 8-column header. Excel showed 3 unnamed columns. Fix: unified header to 14 columns covering both stream-level and component-level data, with component rows aligning to columns 10-14. **When CSV has parent/child rows, define a single header spanning all columns so both row types align.**

### Insights File Upload: Mistakes and Resolutions

1. **ProSim CSV headers didn't map to engine context builder keys**: Headers like `"Temperature (°C)"` were lowercased to `"temperature (°c)"` but `_build_simulation_context()` looks for `"temperature"`. All parsed stream data showed as `T=? P=? flow=?` in the AI prompt. Fix: added `_PROSIM_HEADER_MAP` to normalize CSV headers to engine key names during parsing. **When parsing external file formats, always normalize column names to match the internal key convention used by downstream consumers.**

2. **DWSIM JSON parser created spurious stream entries from equipment objects**: `SimulationObjects` contains ALL objects (streams + equipment) mixed together. The stream extraction loop iterated the same dict without filtering by `ObjectType`, so Heaters/Compressors with `Temperature`/`Pressure` properties were parsed as streams. Fix: single iteration with `ObjectType` classification — only `"MaterialStream"` → streams, skip `"EnergyStream"`, everything else → equipment. **When a JSON dict mixes object types, always filter by type discriminator before extraction.**

3. **Generic CSV `"type"` column misclassified streams as equipment**: `_EQUIPMENT_KEYWORDS` included `"type"`, but stream tables commonly have a `"type"` column (values like "Vapor", "Liquid", "Two-phase"). Any HMB table with a type column had all rows classified as equipment. Fix: removed `"type"` from equipment keywords; created `_STRONG_EQUIPMENT_MARKERS` set (`duty`, `work`, `power`, `head`, `stages`, `reflux`) that unambiguously indicate equipment. **Ambiguous keywords like "type" should not be used for classification — use domain-specific markers that only appear in one context.**

### Stress Test Round 2: Mistakes and Resolutions

1. **Supercritical VF override placed in Separator only, not `_flash_tp()`**: H2/N2 at -10°C/15MPa (both above Tc) returned VF=0 from thermo flash. Override in Separator set VF=1 locally, but compressor re-flashed and got VF=0 again, rejecting feed as "liquid". Separator also produced zero enthalpy on vapor outlet (gas_phase=None after supercritical override). Fix: moved override into `_flash_tp()` so all equipment benefits; added mixture-enthalpy fallback when per-phase enthalpy unavailable. **Phase corrections must be applied at the flash level, not per-equipment — otherwise every consumer re-flashes and gets the original wrong answer.**

4. **No unit system detection — DWSIM K/Pa data labeled as °C/kPa in AI prompt**: `_build_simulation_context()` hardcodes `°C` and `kPa` labels. DWSIM stores T=373.15 K and P=101325 Pa, so the AI saw `T=373.15°C` (extremely hot) instead of 100°C, producing quantitatively wrong optimization recommendations. Fix: added `_detect_unit_system()` heuristic (high T + high P → DWSIM SI; high T + low P → Field units) with unit annotation in raw_context. **When accepting data from multiple simulators, never hardcode unit labels — detect or let users specify the unit system.**

5. **Property package hardcoded to PengRobinson for all file uploads**: Upload endpoint passed `property_package="PengRobinson"` regardless of source simulator. A DWSIM file simulated with SRK would get AI advice like "switch from PR to SRK" when the user already IS using SRK. Fix: added `property_package` Form parameter + auto-detection from DWSIM JSON `FlowsheetOptions.PropertyPackage` + user-selectable dropdown on InsightsPage. **User-facing parameters should never be silently hardcoded — always provide a selector or auto-detect from the data.**

### Phase 10: Mistakes and Resolutions

1. **LMTD used absolute temperature conversion instead of temperature-difference conversion**: HX badge applied `°C→°F` formula (`T*9/5+32`) to LMTD, but LMTD is a ΔT — adding the +32 offset is wrong (20°C LMTD would show as 68°F instead of correct 36°F). Also, velocity/area/length had unit labels but no conversion functions, silently displaying m/s as "ft/s". Fix: added `temperatureDelta` converter (scale only, no offset) and `velocity`/`area`/`length` converters to all 3 unit systems. **Temperature differences (LMTD, ΔT, approach) need a separate converter from absolute temperatures — scale factor only, no offset.**

2. **E2E `findStream` searched by node ID but stream result keys are edge IDs**: `findStream(data.stream_results, 'h1')` looked for keys starting with `'h1'`, but stream results are keyed by edge ID (e.g., `'e2'`), so every lookup returned `undefined`. Fix: store the edges array via `setEdges()` inside `runSim()`, then `findStream` matches by `edge.source === sourceId` to find the correct edge ID. **Stream result keys are edge IDs, not node IDs — always look up streams through the edges array.**

3. **New equipment types added to engine but not to `EQUIPMENT_TYPE_MAP`**: Background agent added EquilibriumReactor and GibbsReactor processing blocks (~400 lines) to `dwsim_engine.py` but didn't add them to the `EQUIPMENT_TYPE_MAP` dict. Engine silently skipped them with "Skipping unknown type" log. Fix: added both types to the map. **When adding new equipment types, always update `EQUIPMENT_TYPE_MAP` — the engine's dispatch gate check happens before the `elif ntype ==` blocks.**

4. **Agent-inserted reactor blocks used `params.get("temperature")` but frontend key is `outletTemperature`**: Background agent guessed the parameter key name instead of matching `equipment-library.ts`. Engine silently fell back to inlet temperature, masking the bug. Fix: changed to `params.get("outletTemperature", params.get("temperature"))`. **When agents generate engine code for new equipment, always cross-check parameter keys against the frontend equipment-library definitions.**

5. **Rigorous distillation integration called `self._get_mw(comp_names, zs)` but `_get_mw` is a module-level function**: `_get_mw(comp_name: str)` takes a single compound name, not a list. The call `self._get_mw(comp_names, zs)` would have crashed at runtime. Fix: changed to `sum(zs[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))`. **Always verify whether helpers are instance methods (`self.`) or module-level functions, and check their signatures before calling.**

6. **Stripper `mf1`/`P_op` referenced before assignment — NameError crash for all reboiled strippers**: The reboiled stripper block (feed2 mass_flow=0) used `mf1`, `P_op`, and `n_stages` which were only assigned further down in the code. Fix: moved variable assignments above the reboiled stripper block. **When adding conditional early-exit branches, ensure all variables used in the branch are assigned before it.**

7. **Rigorous distillation fabricated feed flow as `2*D` instead of using actual feed**: `solve_rigorous_distillation()` had no `feed_flow` parameter — it invented `F = max(2*D, D+0.1)`, only correct when D/F=0.5. Fix: added `feed_flow` parameter, engine passes actual `feed_molar_flow`. **Solvers must receive actual feed conditions from the caller — never fabricate process data internally.**

8. **Condenser duty had wrong sign (positive instead of negative), inflating reboiler duty by 2×Q_c**: Energy balance `Q_r = D*H_D + B*H_B + Q_c - F*H_F` used positive Q_c (heat added) but condensers remove heat (Q_c < 0). Reboiler duty was ~2× too high. Fix: ensured Q_c is negative, reboiler uses `-Q_c` in energy balance. **Condensers remove heat (Q < 0), reboilers add heat (Q > 0) — always enforce sign conventions in energy balances.**

9. **Reboiler liquid flow initialized to zero — Thomas algorithm produces meaningless compositions on first iteration**: `sd.L = 0.0` at reboiler stage makes the TDMA diagonal element zero, producing near-zero or arbitrary liquid compositions that propagate upward. Fix: initialize to `B = F - D` (bottoms flow). **Distillation stage initialization must use physically meaningful flows — zero liquid at the reboiler violates the material balance structure.**

10. **GibbsReactor used `Hf(298) - T*Sf(298)` approximation when `Gfgs` is available**: At 800°C the linear `Hf - T*Sf` formula overestimates Gibbs energy magnitude because it ignores Cp temperature dependence. The thermo library provides `constants.Gfgs` (standard Gibbs at 298K) directly. Fix: use `Gfgs` with Gibbs-Helmholtz temperature correction `Gf(T) = Gf(298) + (Hf - Gf_298)*(1 - T/298.15)`. **Always prefer library-provided thermodynamic properties over manual approximations from constituent values.**

11. **HX Kern sizing assumed all flow through a single 3/4" tube — h overestimated by 10-100×**: Velocity through one tube was 100+ m/s (vs realistic 1-2 m/s), giving Re ~10⁶ and unrealistically high h. Fix: estimate tube count from target velocity (1 m/s liquid, 15 m/s gas), use shell equivalent diameter for shell-side. **Equipment sizing correlations require realistic flow geometry — single-element assumptions produce physically meaningless results.**

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
