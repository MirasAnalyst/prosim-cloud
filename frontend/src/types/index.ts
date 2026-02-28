export enum EquipmentType {
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
}

export enum EquipmentCategory {
  Mixing = 'Mixing',
  HeatTransfer = 'Heat Transfer',
  Separation = 'Separation',
  PressureChange = 'Pressure Change',
  Reaction = 'Reaction',
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
  default: number | string | boolean;
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

export interface StreamConditions {
  temperature: number;
  pressure: number;
  flowRate: number;
  vapor_fraction: number;
  composition: Record<string, number>;
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
