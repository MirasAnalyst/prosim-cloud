# CLAUDE.md

## Project
ProSim Cloud — cloud-based process simulation SaaS (like Aspen HYSYS) with AI co-pilot. Monorepo: `/frontend` (Vite+React+TS, React Flow, Zustand, Tailwind) and `/backend` (FastAPI, SQLAlchemy+psycopg, Supabase PostgreSQL, OpenAI). Backend runs on port 8000, frontend on 5173 with Vite proxy for `/api`.

## Architecture
- **Backend engine**: `backend/app/services/dwsim_engine.py` — simulation engine with thermo library integration. Priority: DWSIM (pythonnet) → thermo (PR/SRK EOS flash) → basic energy/mass balance fallback. Has `_flash_tp()` shared helper, `_normalize_nodes()` for React Flow format, and `_build_feed_from_params()` for user-defined feed conditions.
- **Frontend stores**: Zustand stores in `frontend/src/stores/` — `flowsheetStore.ts` (nodes/edges/persistence), `simulationStore.ts` (run sim/results/property package).
- **Unit convention**: Frontend uses °C/kPa/kW/%. Engine uses K/Pa/W/fraction internally. Conversion helpers (`_c_to_k`, `_kpa_to_pa`, `_w_to_kw`) at I/O boundaries in `dwsim_engine.py`.
- **API routes**: `/api/projects`, `/api/projects/{id}/flowsheet`, `/api/simulation/run`, `/api/compounds/search`, `/api/agent/chat`.
- **Schemas**: `backend/app/schemas/flowsheet.py` (NodeData, EdgeData with camelCase aliases), `backend/app/schemas/simulation.py` (SimulationRequest with property_package).

## Current State (Phase 2 Complete)
- 13 equipment types with thermo-integrated calculations (Heater, Cooler, Mixer, Splitter, Separator, Pump, Compressor, Valve, HeatExchanger, DistillationColumn, CSTRReactor, PFRReactor, ConversionReactor)
- Compound search endpoint with 40+ curated compounds + optional thermo library lookup
- Feed Conditions editor in PropertyInspector (compound search, composition table, auto-normalize)
- Property package selection (Peng-Robinson, SRK, NRTL) — dropdown in TopNav, passed through to engine
- Stream labels on canvas edges (T°C | P kPa | flow kg/s) after simulation
- Equipment result badges on nodes (Q kW, W kW, VF) after simulation
- Flowsheet persistence with debounced auto-save (1s) and project load on mount
- Editable project name in TopNav
- Bottom panel shows simulation logs and stream results table with correct units (kg/s)

## Key Lessons

### Phase 1: Frontend↔Backend Data Contract Mismatches
Built full stack in parallel, then chem-soft review caught 14 critical mismatches: equipment type casing, parameter key naming (camelCase vs snake_case), unit systems, data structure access (`node.parameters` vs `node.data`), and engineering errors. Fix: rewrote `dwsim_engine.py` with unit conversion helpers, matched all keys to frontend conventions. **Always cross-check frontend↔backend data contracts before declaring integration complete.**

### Phase 2: Mistakes and Resolutions

1. **React Flow node format mismatch**: Engine read `node.type` expecting "Heater" but got "equipment" (React Flow wraps actual type in `node.data.equipmentType`). All equipment silently skipped. Fix: added `_normalize_nodes()` to extract `data.equipmentType` into flat `type` field.

2. **Edge handle snake_case vs camelCase**: Pydantic `EdgeData` had `source_handle` (snake_case) but frontend sends `sourceHandle` (camelCase). Handles stored as `None`, breaking stream propagation — separator fell back to 10% VF, stream labels empty. Fix: added `Field(alias="sourceHandle")` + `populate_by_name=True` in schema, and `e.sourceHandle ?? e.source_handle` fallback in frontend loader.

3. **thermo `state.liquid0` AttributeError**: When VF=1.0 (all gas), accessing `state.liquid0` crashes instead of returning None. Flash silently failed, falling back to water Cp=4186. Fix: changed to `getattr(state, 'liquid0', None)` and `getattr(state, 'gas', None)`.

4. **Backend agent never started work**: Spawned 3 parallel agents but the chem-soft backend agent stayed idle. Fix: implemented all backend changes directly as team-lead instead of waiting. Lesson: don't block on a stuck agent — take over the work.

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
```
