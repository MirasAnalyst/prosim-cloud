# ProSim Cloud

Cloud-based process simulation SaaS with an AI co-pilot — like Aspen HYSYS in your browser.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![React](https://img.shields.io/badge/react-19-blue)

## Features

- **Flowsheet Canvas** — Drag-and-drop React Flow canvas with 13 unit operations, custom SVG equipment icons, and animated stream connections
- **13 Equipment Types** — Mixer, Splitter, Heater, Cooler, Separator, Pump, Compressor, Valve, Heat Exchanger, Distillation Column, CSTR, PFR, and Conversion Reactor
- **Property Inspector** — Click any equipment to edit parameters (temperature, pressure, efficiency, etc.) with unit labels
- **Simulation Engine** — FastAPI backend with thermodynamic calculations, unit conversion (°C/kPa/kW ↔ K/Pa/W), topological flowsheet solving, and stream condition propagation
- **AI Co-Pilot** — Chat panel powered by OpenAI for process engineering assistance
- **Supabase PostgreSQL** — Persistent storage for projects, flowsheets, and simulation results

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, React Flow, Zustand, Tailwind CSS 4 |
| Backend | FastAPI, SQLAlchemy (async), Pydantic Settings, Alembic |
| Database | PostgreSQL (Supabase) via psycopg |
| Simulation | thermo library (Peng-Robinson EOS), optional CoolProp/DWSIM |
| AI | OpenAI GPT-4o with streaming SSE |
| Infra | Docker Compose, Vite dev proxy |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL (or a Supabase project)
- OpenAI API key

### Setup

```bash
# Clone
git clone https://github.com/MirasAnalyst/prosim-cloud.git
cd prosim-cloud

# Environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY

# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### Docker

```bash
docker-compose up
```

## Usage

1. **Drag equipment** from the left palette onto the canvas
2. **Connect ports** by dragging from an outlet (right) to an inlet (left)
3. **Edit parameters** by clicking on any equipment
4. **Simulate** by clicking the green button in the top bar
5. **View results** in the expandable bottom panel (logs, stream table)
6. **Ask the AI** by clicking the AI button for process engineering help

## Project Structure

```
prosim-cloud/
├── frontend/                # Vite + React + TypeScript
│   └── src/
│       ├── components/      # Canvas, Equipment, Inspector, Agent, Layout
│       ├── stores/          # Zustand (flowsheet, simulation, agent)
│       ├── lib/             # Equipment library, API client
│       └── types/           # TypeScript interfaces & enums
├── backend/                 # FastAPI + Python
│   └── app/
│       ├── api/routes/      # Projects, Flowsheets, Simulation, Agent
│       ├── models/          # SQLAlchemy models
│       ├── schemas/         # Pydantic schemas
│       ├── services/        # DWSIM engine, OpenAI agent
│       └── core/            # Settings & config
├── docker-compose.yml
├── todo.md                  # Development roadmap (11 phases)
└── CLAUDE.md
```

## Roadmap

See [todo.md](todo.md) for the full 11-phase development plan covering simulation engine enhancements, equipment models, AI co-pilot features, authentication, optimization, and deployment.

## License

MIT
