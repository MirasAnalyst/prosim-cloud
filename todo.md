# ProSim Cloud - Development Roadmap

## Phase 1: Foundation (Current - Complete)

- [x] Project scaffolding (monorepo with `/frontend` + `/backend`)
- [x] Git repository initialization
- [x] Docker Compose setup (PostgreSQL, backend, frontend)
- [x] Dockerfiles for backend (Python 3.11 + Mono) and frontend (Node 20)
- [x] Environment configuration (.env.example, settings)
- [x] TypeScript types (equipment, stream, simulation, agent, project)
- [x] Equipment library with all 13 unit operations
- [x] Zustand stores (flowsheet, agent, simulation)
- [x] React Flow canvas with drag-drop support
- [x] Equipment palette with all unit ops grouped by category
- [x] Property inspector for equipment parameters
- [x] AI agent chat panel with sliding UI
- [x] Layout shell (TopNav, AppLayout, BottomPanel)
- [x] FastAPI backend with CORS
- [x] SQLAlchemy models (Project, Flowsheet, SimulationResult)
- [x] Alembic migration setup
- [x] DWSIM engine wrapper with pythonnet + thermo/CoolProp fallback
- [x] OpenAI agent service with streaming support
- [x] All API routes (projects, flowsheets, simulation, agent)
- [x] Frontend API client for all endpoints
- [x] Frontend-backend integration (stores wired to real API)

## Phase 2: Core Simulation Engine

- [ ] Install and configure DWSIM assemblies in Docker container
- [ ] Test DWSIM pythonnet bridge with simple mixer simulation
- [ ] Implement thermodynamic property package selection (Peng-Robinson, SRK, NRTL, UNIQUAC)
- [ ] Add compound database browser (search + select compounds for streams)
- [ ] Stream composition editor with auto-normalization
- [ ] Mass/energy balance validation before simulation
- [ ] Simulation convergence settings (tolerance, max iterations, solver method)
- [ ] Sequential modular solver for flowsheet topology
- [ ] Recycle stream detection and tear-stream convergence
- [ ] Unit operation validation (e.g., column must have condenser + reboiler specified)
- [ ] Simulation progress reporting via WebSocket
- [ ] Batch simulation mode (parameter sweeps)

## Phase 3: Equipment Model Enhancement

- [ ] **Mixer**: Multi-stream mixing with flash calculation
- [ ] **Splitter**: Split ratio specification, energy balance
- [ ] **Heater/Cooler**: Specify outlet T or duty, phase change handling
- [ ] **Separator**: Three-phase separation (V-L-L), K-value methods
- [ ] **Pump**: Centrifugal pump curves, NPSH calculation, efficiency curves
- [ ] **Compressor**: Polytropic/isentropic modes, multi-stage with intercooling
- [ ] **Valve**: Isenthalpic flash, Cv calculation, choked flow detection
- [ ] **Heat Exchanger**: LMTD and effectiveness-NTU methods, shell & tube geometry
- [ ] **Distillation Column**: Full MESH equations, multiple feeds/sidedraws, condenser/reboiler types
- [ ] **CSTR Reactor**: Reaction kinetics, heat of reaction, jacket cooling
- [ ] **PFR Reactor**: Axial profile, pressure drop, heat transfer along length
- [ ] **Conversion Reactor**: Stoichiometric conversion, multiple reactions
- [ ] Add new equipment: Absorber, Stripper, Crystallizer, Dryer, Cyclone, Filter
- [ ] Equipment sizing calculations (diameter, height, area)
- [ ] Equipment costing (CAPEX estimation via correlations)

## Phase 4: AI Co-Pilot Enhancement

- [ ] Context-aware flowsheet understanding (AI reads current flowsheet state)
- [ ] Natural language flowsheet building ("Add a heat exchanger between the pump and the column")
- [ ] AI-driven equipment parameter suggestions based on industry standards
- [ ] Simulation troubleshooting assistant (diagnose convergence failures)
- [ ] Process optimization suggestions (energy recovery, heat integration)
- [ ] AI-generated simulation reports
- [ ] Function calling: AI directly modifies flowsheet via tool calls
- [ ] Conversation memory (persist chat history per project in DB)
- [ ] Multi-model support (GPT-4o, Claude, local LLMs via Ollama)
- [ ] RAG integration with engineering reference data

## Phase 5: User Interface Polish

- [ ] Undo/redo system for flowsheet changes
- [ ] Copy/paste equipment and sub-flowsheets
- [ ] Stream labels showing T, P, flow on canvas
- [ ] Color-coded streams by phase (blue=liquid, red=vapor, green=two-phase)
- [ ] Equipment status indicators (converged, error, not-calculated)
- [ ] Zoom-to-fit and auto-layout algorithms
- [ ] Dark/light theme toggle
- [ ] Keyboard shortcuts (Delete, Ctrl+Z, Ctrl+S, etc.)
- [ ] Canvas grid snapping
- [ ] Equipment grouping / sub-flowsheets
- [ ] Stream tables (sortable, exportable)
- [ ] PFD annotation tools (text boxes, labels, lines)
- [ ] Responsive design for tablets
- [ ] Loading skeletons and optimistic UI updates
- [ ] Toast notifications for simulation events

## Phase 6: Data & Persistence

- [ ] Project save/load (auto-save with debounce)
- [ ] Project versioning (save snapshots, diff between versions)
- [ ] Export flowsheet as JSON, XML, or DWSIM native format
- [ ] Import DWSIM .dwxmz files
- [ ] Export simulation results to CSV/Excel
- [ ] Export PFD as SVG/PNG/PDF
- [ ] Database migrations for schema evolution
- [ ] Data validation and integrity checks
- [ ] Backup and restore functionality

## Phase 7: Authentication & Multi-Tenancy

- [ ] User authentication (JWT + refresh tokens)
- [ ] OAuth2 login (Google, GitHub, Microsoft)
- [ ] User registration and email verification
- [ ] Role-based access control (admin, engineer, viewer)
- [ ] Team/organization management
- [ ] Project sharing and collaboration
- [ ] Real-time collaborative editing (WebSocket-based)
- [ ] Audit logging (who changed what, when)
- [ ] API rate limiting per user/tier

## Phase 8: Advanced Simulation Features

- [ ] Dynamic simulation (time-dependent transient modeling)
- [ ] Sensitivity analysis (automatic parameter variation + plotting)
- [ ] Optimization (objective function + constraints, SQP/genetic algorithms)
- [ ] Case studies (compare multiple scenarios side by side)
- [ ] Pinch analysis / heat integration tools
- [ ] Utility system modeling (steam, cooling water, electricity)
- [ ] Environmental calculations (emissions, flaring)
- [ ] Relief valve sizing
- [ ] Hydraulic calculations (pipe sizing, pressure drop)
- [ ] Control valve sizing

## Phase 9: Visualization & Reporting

- [ ] Stream property charts (T-xy, P-xy, McCabe-Thiele)
- [ ] Equipment performance curves
- [ ] Interactive Sankey diagrams for energy/mass flow
- [ ] Column profile plots (temperature, composition vs. stage)
- [ ] Reactor conversion/selectivity plots
- [ ] Heat exchanger temperature profiles
- [ ] Automated simulation report generation (PDF)
- [ ] Dashboard with key performance indicators
- [ ] Real-time data trending (for dynamic simulations)
- [ ] Comparison charts across case studies

## Phase 10: Deployment & DevOps

- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Automated testing (unit, integration, e2e with Playwright)
- [ ] Backend unit tests (pytest + httpx)
- [ ] Frontend unit tests (Vitest + React Testing Library)
- [ ] End-to-end tests for simulation workflows
- [ ] Production Docker images (multi-stage builds, optimized)
- [ ] Kubernetes deployment manifests
- [ ] SSL/TLS configuration
- [ ] CDN for static assets
- [ ] Database connection pooling + read replicas
- [ ] Monitoring and alerting (Prometheus, Grafana)
- [ ] Error tracking (Sentry integration)
- [ ] Performance profiling and optimization
- [ ] API documentation (auto-generated OpenAPI/Swagger)
- [ ] User documentation and tutorials

## Phase 11: Enterprise Features

- [ ] On-premise deployment option
- [ ] LDAP/Active Directory integration
- [ ] SSO (SAML 2.0)
- [ ] Custom thermodynamic property packages
- [ ] Plugin system for custom unit operations
- [ ] Batch processing API
- [ ] Webhook integrations
- [ ] Usage analytics and metering
- [ ] SLA monitoring
- [ ] White-labeling support
