# CLAUDE.md

## Project
ProSim Cloud — cloud-based process simulation SaaS (like Aspen HYSYS) with AI co-pilot. Monorepo: `/frontend` (Vite+React+TS, React Flow, Zustand, Tailwind) and `/backend` (FastAPI, SQLAlchemy+psycopg, Supabase PostgreSQL, OpenAI). Backend runs on port 8000, frontend on 5173 with Vite proxy for `/api`.

## Key Lesson
Built full stack in parallel (frontend-dev + backend-dev agents), then chem-soft review caught 14 critical mismatches: equipment type casing (PascalCase vs snake_case), parameter key naming (camelCase vs snake_case), unit systems (°C/kPa/kW vs K/Pa/W), data structure access (`node.parameters` vs `node.data`), response key names, and engineering errors (mixer enthalpy balance, valve JT effect, flash drum mass split). Fix approach: rewrote `dwsim_engine.py` with unit conversion helpers at I/O boundaries, matched all keys to frontend conventions, added missing equipment handlers (PFR/Conversion/Separator), and made enthalpy propagation consistent across equipment chain. Always cross-check frontend↔backend data contracts before declaring integration complete.
