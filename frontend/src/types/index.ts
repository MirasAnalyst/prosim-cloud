export enum EquipmentType {
  FeedStream = 'FeedStream',
  ProductStream = 'ProductStream',
  Mixer = 'Mixer',
  Splitter = 'Splitter',
  Heater = 'Heater',
  Cooler = 'Cooler',
  Separator = 'Separator',
  Pump = 'Pump',
  Compressor = 'Compressor',
  Valve = 'Valve',
  HeatExchanger = 'HeatExchanger',
  DistillationColumn = 'DistillationColumn',
  CSTRReactor = 'CSTRReactor',
  PFRReactor = 'PFRReactor',
  ConversionReactor = 'ConversionReactor',
  Absorber = 'Absorber',
  Stripper = 'Stripper',
  Cyclone = 'Cyclone',
  ThreePhaseSeparator = 'ThreePhaseSeparator',
  Crystallizer = 'Crystallizer',
  Dryer = 'Dryer',
  Filter = 'Filter',
  DesignSpec = 'DesignSpec',
  PipeSegment = 'PipeSegment',
  EquilibriumReactor = 'EquilibriumReactor',
  GibbsReactor = 'GibbsReactor',
}

export enum EquipmentCategory {
  Streams = 'Streams',
  Mixing = 'Mixing',
  HeatTransfer = 'Heat Transfer',
  Separation = 'Separation',
  PressureChange = 'Pressure Change',
  Reaction = 'Reaction',
  Logical = 'Logical',
  Piping = 'Piping',
}

export interface PortDefinition {
  id: string;
  name: string;
  position: 'top' | 'bottom' | 'left' | 'right';
  type: 'inlet' | 'outlet';
}

export interface ParameterDefinition {
  label: string;
  unit: string;
  default: number | string | boolean | null;
  min?: number;
  max?: number;
  type: 'number' | 'string' | 'boolean';
}

export interface EquipmentDefinition {
  type: EquipmentType;
  label: string;
  category: EquipmentCategory;
  icon: string;
  parameters: Record<string, ParameterDefinition>;
  ports: PortDefinition[];
}

export interface EquipmentData {
  id: string;
  type: EquipmentType;
  name: string;
  parameters: Record<string, number | string | boolean>;
  position: { x: number; y: number };
}

export interface PhaseProperties {
  density?: number | null;
  viscosity?: number | null;
  thermal_conductivity?: number | null;
  Cp?: number | null;
  Cv?: number | null;
  enthalpy?: number | null;
  entropy?: number | null;
  Z?: number | null;
  composition?: Record<string, number>;
}

export interface StreamConditions {
  temperature: number;
  pressure: number;
  flowRate: number;
  vapor_fraction: number;
  composition: Record<string, number>;
  enthalpy?: number;
  entropy?: number;
  molecular_weight?: number;
  molar_flow?: number;
  mass_fractions?: Record<string, number>;
  component_molar_flows?: Record<string, number>;
  component_mass_flows?: Record<string, number>;
  // Transport properties
  density?: number | null;
  viscosity?: number | null;
  thermal_conductivity?: number | null;
  surface_tension?: number | null;
  Cp_mass?: number | null;
  Cv_mass?: number | null;
  Z_factor?: number | null;
  volumetric_flow?: number | null;
  // Phase-specific properties
  phase_properties?: {
    liquid: PhaseProperties;
    vapor: PhaseProperties;
  };
}

export interface StreamData {
  id: string;
  name: string;
  sourceId: string;
  sourcePort: string;
  targetId: string;
  targetPort: string;
  conditions: StreamConditions;
}

export enum SimulationStatus {
  Idle = 'idle',
  Running = 'running',
  Completed = 'completed',
  Error = 'error',
}

export interface SimulationResult {
  streamResults: Record<string, StreamConditions>;
  equipmentResults: Record<string, Record<string, number | string>>;
  convergenceInfo: {
    iterations: number;
    converged: boolean;
    error: number;
    history?: Array<{ iteration: number; max_error: number; [key: string]: number }>;
    mass_balance_ok?: boolean;
    energy_balance_ok?: boolean;
    recycle_detected?: boolean;
    tear_streams?: number;
  };
  logs: string[];
}

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  flowsheetAction?: { equipmentCount: number; connectionCount: number };
}

export interface Project {
  id: string;
  name: string;
  description: string;
  flowsheet: {
    equipment: EquipmentData[];
    streams: StreamData[];
  };
  createdAt: Date;
  updatedAt: Date;
}
