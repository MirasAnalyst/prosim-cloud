# ProSim Cloud - Development Roadmap

> **Status as of Mar 2026:**
> - Phase 1: Complete
> - Phase 2: Complete (convergence settings UI, SSE progress, batch simulation, UNIQUAC, tear-stream convergence, mass/energy balance)
> - Phase 3: Complete (24 equipment types, HX NTU, reactor kinetics, pump curves, multi-stage compressor, valve Cv, equipment costing)
> - Phase 4: Complete (AI flowsheet generation, optimization suggestions, PDF reports, multi-model AI, RAG, troubleshooting assistant)
> - Phase 5: Complete (undo/redo, copy/paste, dark/light theme, equipment grouping, PFD annotations, responsive design, loading skeletons)
> - Phase 6: Complete (versioning, export JSON/XML/DWSIM, import, results CSV/Excel, PFD SVG/PNG/PDF, validation, backup/restore)
> - Phase 8: ~93% (13 of 14 items done; missing: product stream specs)
> - Phase 9: Complete (Unit Op Correctness Audit — 27 engine fixes across 3 waves)
> - Phase 10: ~79% (Tier 1: 100%, Tier 2: 100%, Tier 3: ~33%, Tier 4: 0%)
> - Phase 7, 11–12: Not started
> - **130 E2E tests** across 26 spec files (complex-industrial 16, industrial-flowsheets 16, stress-20 20, unit-system 20, equipment-coverage 10, phase8-remaining 9, insights 4, dark-theme 1, + 34 legacy)

## Phase 1: Foundation (Complete)

- [x] Project scaffolding (monorepo with `/frontend` + `/backend`)
- [x] Git repository initialization
- [x] Docker Compose setup (PostgreSQL, backend, frontend)
- [x] Dockerfiles for backend (Python 3.11 + Mono) and frontend (Node 20)
- [x] Environment configuration (.env.example, settings)
- [x] TypeScript types (equipment, stream, simulation, agent, project)
- [x] Equipment library with all 20 unit operations
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

## Phase 2: Core Simulation Engine (Complete)

- [x] Install and configure DWSIM assemblies in Docker container *(N/A — using `thermo` library, covers all needs)*
- [x] Test DWSIM pythonnet bridge with simple mixer simulation *(N/A — using `thermo` library)*
- [x] Implement thermodynamic property package selection (Peng-Robinson, SRK, NRTL, UNIQUAC) *(GibbsExcessLiquid with NRTLModel/UNIQUACModel, BIPs from IPDB)*
- [x] UNIQUAC property package support *(UNIQUACModel with UNIFAC_Rs/UNIFAC_Qs, zero-matrix BIP fallback)*
- [x] Add compound database browser (search + select compounds for streams) *(40+ curated compounds + thermo lookup)*
- [x] Stream composition editor with auto-normalization
- [x] Mass/energy balance validation *(post-loop check of sum(inlet flows) vs sum(outlet flows) per node)*
- [x] Feed composition validation *(auto-normalize if total ≠ 1.0, block if empty, warnings in logs)*
- [x] Per-equipment error isolation *(individual failures return `{"error": str}` without losing other results)*
- [x] Division-by-zero guards *(pump rho≤0, compressor P_in≤0 / P_out<P_in, mf≤0 clamped to 1e-10)*
- [x] Simulation convergence settings (tolerance, max iterations, damping) *(gear icon popover in TopNav, ConvergenceSettings schema, passed through to engine)*
- [x] Sequential modular solver for flowsheet topology *(topological sort with `_topological_sort()`)*
- [x] Recycle stream detection and tear-stream convergence *(Wegstein acceleration clamped [-5, 0.9], damping, max iterations)*
- [x] Unit operation validation *(Mixer ≥2 inlets, HX 2 inlets, Splitter ≥2 outlets, WARNING logs)*
- [x] Simulation progress reporting via SSE *(POST /api/simulation/run/stream, progress bar in BottomPanel)*
- [x] Batch simulation mode (parameter sweeps) *(POST /api/simulation/batch, cartesian product of variations)*

## Phase 3: Equipment Model Enhancement (Complete)

- [x] **Mixer**: Multi-stream mixing with flash calculation *(molar-weighted composition, HP flash for outlet T)*
- [x] **Splitter**: Split ratio specification, energy balance
- [x] **Heater/Cooler**: Specify outlet T or duty, phase change handling *(HP flash for duty mode, VF tracking)*
- [x] **Separator**: Two-phase V-L separation with flash
- [x] **ThreePhaseSeparator**: Three-phase V-L-L separation *(flash + MW-based liquid splitting, 3 outlets)*
- [x] **Pump**: Centrifugal pump with NPSH calculation *(flash-based density, rated flow/head, NPSH warning)*
- [x] **Compressor**: Multi-stage isentropic with intercooling *(per-stage compression, ratio splitting, work summation)*
- [x] **Valve**: Isenthalpic flash, Cv calculation, choked flow detection *(HP flash for JT cooling, Cv = Q·√(SG/ΔP), choked flow FF check)*
- [x] **Heat Exchanger**: LMTD and NTU methods, fouling *(NTU with shell-tube/plate geometry correlations, fouling factor R_f)*
- [x] **Distillation Column**: FUG shortcut with bubble-point K-values *(Fenske-Underwood-Gilliland, proper component split)*
- [x] **CSTR Reactor**: Arrhenius kinetics, jacket heat transfer *(k=A·exp(-Ea/RT), X=τk/(1+τk), Q_jacket=UA·(Tj-T))*
- [x] **PFR Reactor**: Arrhenius kinetics, Ergun pressure drop *(dP/dz from Blake-Kozeny + Burke-Plummer, X=1-exp(-kτ))*
- [x] **Conversion Reactor**: Multiple reactions support *(JSON reactions array applied sequentially)*
- [x] **Absorber**: Kremser equation *(A=L/(mG), K-values from flash, 4 ports)*
- [x] **Stripper**: Kremser equation *(4 ports, rich solvent + stripping gas)*
- [x] **Cyclone**: Shepherd-Lapple pressure drop *(ΔP = K·ρ·V²/2, 2 outlets)*
- [x] **Crystallizer**: Temperature-based crystallization *(flash at crystallization temp, crystal yield proportional to ΔT)*
- [x] **Dryer**: Moisture removal with enthalpy balance *(Q = m_water_removed · h_vap, 2 outlets)*
- [x] **Filter**: Efficiency-based mass split *(filtrate/cake separation, pressure drop applied)*
- [x] Equipment sizing calculations *(Souders-Brown separators, A=Q/(U·LMTD) HX, Fair's flooding columns)*
- [x] Equipment costing (CAPEX estimation) *(CEPCI-adjusted Seider correlations for Pump, Compressor, HX, Column, Separator)*

## Phase 4: AI Co-Pilot Enhancement (Complete)

- [x] Context-aware flowsheet understanding *(~500 token summarization)*
- [x] Natural language flowsheet building *(OpenAI tools API, 6 few-shot examples, add/replace modes)*
- [x] AI compound name validation *(42 exact names in system prompt)*
- [x] Simulation troubleshooting assistant *(expert rules for convergence diagnosis, 9 equipment failure patterns, property package guidance)*
- [x] Process optimization suggestions *(suggest_optimizations tool: energy recovery, efficiency, pressure optimization, reflux tuning, cost reduction)*
- [x] AI-generated simulation reports *(POST /api/simulation/report, PDF via reportlab with text fallback)*
- [x] Conversation memory *(ChatMessage model, GET/POST/DELETE endpoints)*
- [x] Multi-model support *(AIProvider abstraction: OpenAI, Claude via anthropic SDK, Ollama via httpx)*
- [x] RAG integration with engineering reference data *(in-memory hash embeddings, 10 reference docs, cosine similarity)*

## Phase 5: User Interface Polish (Complete)

- [x] Undo/redo system *(history[] with 50-cap, pushHistory on addNode/removeNode/onConnect, Ctrl+Z/Ctrl+Shift+Z)*
- [x] Copy/paste equipment *(clipboard with re-UUID + 40px offset, Ctrl+C/Ctrl+V)*
- [x] Stream labels showing T, P, flow on canvas *(T°C | P kPa | flow kg/s)*
- [x] Color-coded streams by phase *(blue liquid, red gas, orange two-phase)*
- [x] Equipment status indicators *(result badges: Q/W kW, VF, LK%, X%, ratio, flow, ΔP, yield%, moisture%)*
- [x] Zoom-to-fit and auto-layout *(Kahn's longest-path left-to-right layout)*
- [x] Color-coded simulation logs *(WARNING=yellow, ERROR=red in BottomPanel)*
- [x] Simulation timeout and cancel button *(60s AbortController + Cancel in TopNav)*
- [x] Input value clamping *(min/max from paramDef on blur, red border)*
- [x] Editable project name in TopNav
- [x] Save status indicator *(green/yellow/red dot)*
- [x] Clear chat button in AgentPanel
- [x] Dark/light theme toggle *(themeStore with localStorage, Sun/Moon toggle, Tailwind dark: variant)*
- [x] Keyboard shortcuts *(Ctrl+S save, Ctrl+Enter simulate, Escape deselect, Ctrl+Z/Y undo/redo, Ctrl+C/V copy/paste)*
- [x] Canvas grid snapping *(snapToGrid snapGrid={[20, 20]})*
- [x] Equipment grouping *(groups[] in flowsheetStore, GroupNode with dashed border, collapse/expand)*
- [x] Stream tables (sortable, exportable) *(click-to-sort headers, CSV export)*
- [x] PFD annotation tools *(annotationStore with text/arrow/rect, draggable AnnotationLayer)*
- [x] Responsive design *(hidden sidebar on mobile, hamburger menu, responsive breakpoints)*
- [x] Loading skeletons *(animated pulse bars during simulation in BottomPanel + EquipmentNode)*
- [x] Toast notifications *(sonner library, toasts on sim complete/error and AI flowsheet apply)*

## Phase 6: Data & Persistence (Complete)

- [x] Project save/load (auto-save with debounce) *(1s debounce, save status indicator in TopNav)*
- [x] Project versioning (save snapshots, diff between versions) *(FlowsheetVersion model, 6 API endpoints, VersionPanel slide-out, versionStore)*
- [x] Export flowsheet as JSON, XML, or DWSIM native format *(GET /export?format=, flowsheet_exporter.py)*
- [x] Import DWSIM .dwxmz files *(POST /import multipart, dwsim_importer.py: ZIP/XML/JSON parsers)*
- [x] Export simulation results to CSV/Excel *(CSV client-side, Excel via openpyxl POST /simulation/export)*
- [x] Export PFD as SVG/PNG/PDF *(html-to-image + jsPDF, canvas-export.ts)*
- [x] Database migrations for schema evolution *(Alembic)*
- [x] Data validation and integrity checks *(flowsheet_validator.py + flowsheet-validator.ts, POST /flowsheet/validate)*
- [x] Backup and restore functionality *(GET /backup, POST /restore, backup_service.py)*

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

## Phase 8: Advanced Simulation Features (~93%)

- [x] Material Stream nodes *(FeedStream/ProductStream types, SVG icons, processed before/after equipment loop)*
- [x] Global Component List / Simulation Basis Manager *(simulation_basis JSONB column, SimulationBasisPanel, compound search, property package selector)*
- [x] Energy Stream connections *(EnergyStreamEdge dashed orange, energy ports on Heater/Cooler/Pump/Compressor/HX/Column)*
- [ ] Product stream specifications (output stream nodes with target specs like purity or flow rate that the solver can back-calculate)
- [x] Dynamic simulation *(POST /simulation/dynamic, pseudo-dynamic step-response, DynamicPanel with disturbances + tracked outputs + Recharts time series)*
- [x] Sensitivity analysis *(POST /simulation/sensitivity, sensitivity_engine.py numpy linspace, SensitivityPanel with recharts LineChart)*
- [x] Optimization *(POST /simulation/optimize, scipy SLSQP + differential_evolution, OptimizationPanel)*
- [x] Case studies *(SimulationCase model, CRUD + compare API, CaseManagerPanel save/load/compare)*
- [x] Pinch analysis / heat integration *(POST /simulation/pinch, Problem Table Algorithm, composite + grand composite curves, PinchPanel)*
- [x] Utility system modeling *(POST /simulation/utility, auto-extract duties, categorize steam/CW/electricity with costs, UtilityPanel)*
- [x] Environmental calculations *(POST /simulation/emissions, EPA AP-42 combustion + LDAR fugitive, IPCC GWP, EmissionsPanel)*
- [x] Relief valve sizing *(POST /simulation/relief-valve, API 520/521/526 gas/liquid sizing, ReliefValvePanel)*
- [x] Hydraulic calculations *(POST /simulation/hydraulics, Churchill + Lockhart-Martinelli two-phase, HydraulicsPanel)*
- [x] Control valve sizing *(POST /simulation/control-valve, ISA 60534 liquid/gas with choked flow, ControlValvePanel)*

## Phase 9: Unit Operation Correctness Audit (Complete)

- [x] 27 engine fixes across 3 waves (5 critical + 9 high + 10 medium + 3 low)
- [x] Wave 1 Critical: multi-stage compressor entropy, distillation condenser Hvap, dryer mole→mass, crystallizer solubility, absorber Kremser molar basis
- [x] Wave 2 High: CSTR/PFR Arrhenius, HX enthalpy-based T, ThreePhaseSep lightLiquidFraction, Filter solidsFraction, Cyclone composition-aware, Compressor gamma, Absorber/Stripper VF, HX NTU area param
- [x] Wave 3 Medium: Mixer Cp fallback, Separator pressureDrop, Pump entropy near-critical, Valve gas Cv, Distillation partial condenser, NRTL aij, Compressor liquid guard, PipeSegment heat loss, Energy balance HX skip

## Phase 11: Visualization & Reporting

- [~] Stream property charts (T-xy, P-xy) *(partial: phase_envelope.py has Txy/Pxy functions)*
- [ ] McCabe-Thiele diagrams
- [ ] Equipment performance curves
- [ ] Interactive Sankey diagrams for energy/mass flow
- [ ] Column profile plots (temperature, composition vs. stage)
- [ ] Reactor conversion/selectivity plots
- [ ] Heat exchanger temperature profiles
- [x] Automated simulation report generation (PDF) *(POST /simulation/report, reportlab)*
- [ ] Dashboard with key performance indicators
- [ ] Real-time data trending (for dynamic simulations)
- [ ] Comparison charts across case studies

## Phase 10: HYSYS/DWSIM Parity

### Tier 1 — Critical (blocks professional use) — 100%
- [x] T1-1: Complete stream properties (viscosity, conductivity, surface tension, density, S, Cp, Cv, Z, MW, phase-specific) *(30+ properties from flash, per-phase liquid/vapor, volumetric flow)*
- [x] T1-2: Full compound database (expose thermo's 4000+ compounds, keep 42 as favorites) *(80 curated + chemicals.search_chemical, /info endpoint, /favorites endpoint)*
- [x] T1-3: Rigorous distillation (BP MESH method, stage-by-stage, multi-feed/side-draw support) *(Wang-Henke BP method, Thomas TDMA, enthalpy balance flow corrections, 100 max iterations)*
- [x] T1-4: Phase envelope & property diagrams (PT envelope, bubble/dew curves) *(POST /phase-envelope, PhaseEnvelopePanel with recharts, cricondentherm/bar/critical)*
- [x] T1-5: Flash type expansion (PH, PS, PVF, TVF flashes in _flash_tp helpers) *(_flash_ph, _flash_ps, _flash_pvf, _flash_tvf helpers)*

### Tier 2 — Important (limits accuracy/usability) — 100%
- [x] T2-1: Proper reaction stoichiometry (stoichiometric matrix, heat of reaction) *(reactions array with reactants/products/coefficients/heatOfReaction, proper mole balance)*
- [x] T2-2: Transport properties in equipment sizing (Kern HX, Ergun PFR, Stokes settling, Lapple d50) *(Kern/shell-side HTC, Separator/ThreePhaseSep/Cyclone settling, flash-derived μ/k/σ/ρ)*
- [x] T2-3: BIP management & validation (UI editor, missing BIP warnings) *(BIP override endpoint, symmetry for cubic EOS, asymmetric NRTL/UNIQUAC, zero-matrix fallback with warnings)*
- [x] T2-4: Configurable unit system (SI, Field, CGS, custom) *(unitStore with localStorage, SI/Field/CGS selector in TopNav, conversions in BottomPanel/StreamEdge/EquipmentNode/StreamInspector/PropertyInspector)*
- [x] T2-5: Convergence diagnostics (variable tracking, error plots) *(convergence_history per iteration, error/T/P/flow tracking, recharts log-scale plot in BottomPanel)*
- [x] T2-6: Multi-feed/side-draw columns *(multi-feed StageData, additional_feeds in rigorous solver, side draw flow modification in TDMA, frontend in-2/out-3 ports)*
- [x] T2-7: Equilibrium reactor & Gibbs minimization *(EquilibriumReactor with Kp + Van't Hoff, GibbsReactor with SLSQP + analytical gradient, pressure correction for Δν≠0)*

### Tier 3 — Engineering Features (professional polish) — ~33%
- [ ] T3-1: Petroleum characterization (pseudo-components from assay data)
- [ ] T3-2: Equipment rating mode (geometry → performance)
- [~] T3-3: Property package advisor (decision tree) *(partial: troubleshooting assistant has property package guidance rules in AI system prompt)*
- [~] T3-4: Txy/Pxy binary VLE diagrams *(partial: phase_envelope.py has generate_txy/generate_pxy functions, endpoint exists)*
- [ ] T3-5: Equipment datasheets (API/TEMA format PDF)
- [ ] T3-6: Stream property tables (per-phase properties)

### Tier 4 — Nice-to-Have
- [ ] Column internals design
- [ ] HEN synthesis from pinch analysis
- [ ] Compressor performance maps
- [ ] Custom unit operations (user Python blocks)
- [ ] CAPE-OPEN interoperability
- [ ] Integrated cost estimation
- [ ] Scripting/automation API

## Phase 12: Deployment & DevOps

- [ ] CI/CD pipeline (GitHub Actions)
- [~] Automated testing (unit, integration, e2e with Playwright) *(68 E2E tests, unit tests not yet)*
- [ ] Backend unit tests (pytest + httpx)
- [ ] Frontend unit tests (Vitest + React Testing Library)
- [x] End-to-end tests for simulation workflows *(130 Playwright tests across 26 spec files)*
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

## Phase 13: Enterprise Features

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
