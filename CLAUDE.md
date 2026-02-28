# CLAUDE.md

## Project
ProSim Cloud — cloud-based process simulation SaaS (like Aspen HYSYS) with AI co-pilot. Monorepo: `/frontend` (Vite+React+TS, React Flow, Zustand, Tailwind) and `/backend` (FastAPI, SQLAlchemy+psycopg, Supabase PostgreSQL, OpenAI). Backend runs on port 8000, frontend on 5173 with Vite proxy for `/api`.

## Architecture
- **Backend engine**: `backend/app/services/dwsim_engine.py` (~1420 lines) — simulation engine with thermo library integration. Priority: DWSIM (pythonnet) → thermo (PR/SRK EOS flash) → basic energy/mass balance fallback. Key internals:
  - `_flash_tp()` — shared TP flash helper returning H, S, Cp, VF, rho_liquid, flasher object, MW_mix. Uses `FlashPureVLS` for single-component, `FlashVL` for mixtures.
  - `_normalize_nodes()` — converts React Flow `{type:"equipment", data:{equipmentType}}` to flat `{type:"Heater"}` format.
  - `_build_feed_from_params()` — builds SI feed from user params with thermo flash for real enthalpy.
  - `_get_mw()` — cached molecular weight lookup (thermo + builtin table of 40+ compounds).
  - `_estimate_cp()` — composition-weighted Cp fallback when thermo unavailable.
- **Frontend stores**: Zustand stores in `frontend/src/stores/` — `flowsheetStore.ts` (nodes/edges/persistence), `simulationStore.ts` (run sim/results/property package).
- **Unit convention**: Frontend uses °C/kPa/kW/%. Engine uses K/Pa/W/fraction internally. Conversion helpers (`_c_to_k`, `_kpa_to_pa`, `_w_to_kw`) at I/O boundaries in `dwsim_engine.py`.
- **API routes**: `/api/projects`, `/api/projects/{id}/flowsheet`, `/api/simulation/run`, `/api/compounds/search`, `/api/agent/chat`.
- **Schemas**: `backend/app/schemas/flowsheet.py` (NodeData, EdgeData with camelCase aliases), `backend/app/schemas/simulation.py` (SimulationRequest with property_package).
- **E2E tests**: `frontend/e2e/` with Playwright config in `frontend/playwright.config.ts`. Tests call `/api/simulation/run` in-browser and verify result correctness + UI rendering.

## Current State (Phase 4 Complete)
- 13 equipment types with thermo-integrated calculations (Heater, Cooler, Mixer, Splitter, Separator, Pump, Compressor, Valve, HeatExchanger, DistillationColumn, CSTRReactor, PFRReactor, ConversionReactor)
- Compound search endpoint with 40+ curated compounds + optional thermo library lookup
- Feed Conditions editor in PropertyInspector (compound search, composition table, auto-normalize)
- Property package selection (Peng-Robinson, SRK, NRTL) — dropdown in TopNav, passed through to engine
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

1. **GPT-4o returned empty parameters**: Tool schema had `parameters` as optional with `additionalProperties: True` — model skipped populating it. Fix: made `parameters` required and added a few-shot example in the system prompt showing populated params.

2. **`_normalize_nodes()` read `data.label` but nodes store `data.name`**: All AI-generated equipment showed UUIDs instead of display names in simulation logs. Fix: changed to `data.get("name", data.get("label", ...))`.

3. **`loadFlowsheet()` never called `debounceSave()`**: AI-generated flowsheets were lost on page refresh — every other mutation triggered auto-save except this one. Fix: added `debounceSave(get)` after `set()`.

4. **`model_dump()` included None fields in follow-up OpenAI call**: Could cause API errors from extra null fields like `refusal`, `audio`. Fix: changed to `model_dump(exclude_none=True)`.

5. **AI couldn't generate CSTR, PFR, or DistillationColumn**: GPT-4o returned text instead of calling the tool for complex equipment. Fix: added few-shot examples for all three in the system prompt (Examples 4–6). All three now generate and converge.

6. **Mixer/HeatExchanger only received one feed stream**: Tool schema couldn't represent two independent feeds per equipment. Fix: taught the AI to create Heater pass-through nodes (outletTemperature=feedTemperature) as feed sources for each inlet, with dedicated examples (Examples 2–3). Mixer now shows correct 2 kg/s total flow; HX now computes correct cold outlet temperature.

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
