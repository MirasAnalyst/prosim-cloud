import { EquipmentType, EquipmentCategory, EquipmentDefinition, ParameterDefinition } from '../types';

const feedConditionParams: Record<string, ParameterDefinition> = {
  feedTemperature: { label: 'Feed Temperature', unit: '°C', default: 25, min: -273.15, max: 2000, type: 'number' },
  feedPressure: { label: 'Feed Pressure', unit: 'kPa', default: 101.325, min: 0, max: 100000, type: 'number' },
  feedFlowRate: { label: 'Feed Flow Rate', unit: 'kg/s', default: 1.0, min: 0, max: 100000, type: 'number' },
};

export const equipmentLibrary: Record<EquipmentType, EquipmentDefinition> = {
  [EquipmentType.Mixer]: {
    type: EquipmentType.Mixer,
    label: 'Mixer',
    category: EquipmentCategory.Mixing,
    icon: 'GitMerge',
    parameters: {
      ...feedConditionParams,
      pressure: { label: 'Outlet Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      pressureDrop: { label: 'Pressure Drop', unit: 'kPa', default: 0, min: 0, max: 1000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed 1', position: 'left', type: 'inlet' },
      { id: 'in-2', name: 'Feed 2', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Splitter]: {
    type: EquipmentType.Splitter,
    label: 'Splitter',
    category: EquipmentCategory.Mixing,
    icon: 'GitBranch',
    parameters: {
      ...feedConditionParams,
      splitRatio: { label: 'Split Ratio (Stream 1)', unit: '', default: 0.5, min: 0, max: 1, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product 1', position: 'right', type: 'outlet' },
      { id: 'out-2', name: 'Product 2', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Heater]: {
    type: EquipmentType.Heater,
    label: 'Heater',
    category: EquipmentCategory.HeatTransfer,
    icon: 'Flame',
    parameters: {
      ...feedConditionParams,
      outletTemperature: { label: 'Outlet Temperature', unit: '°C', default: 100, min: -273.15, max: 2000, type: 'number' },
      duty: { label: 'Heat Duty', unit: 'kW', default: 0, min: 0, max: 1e8, type: 'number' },
      pressureDrop: { label: 'Pressure Drop', unit: 'kPa', default: 0, min: 0, max: 1000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Cooler]: {
    type: EquipmentType.Cooler,
    label: 'Cooler',
    category: EquipmentCategory.HeatTransfer,
    icon: 'Snowflake',
    parameters: {
      ...feedConditionParams,
      outletTemperature: { label: 'Outlet Temperature', unit: '°C', default: 25, min: -273.15, max: 2000, type: 'number' },
      duty: { label: 'Heat Duty', unit: 'kW', default: 0, min: 0, max: 1e8, type: 'number' },
      pressureDrop: { label: 'Pressure Drop', unit: 'kPa', default: 0, min: 0, max: 1000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Separator]: {
    type: EquipmentType.Separator,
    label: 'Separator',
    category: EquipmentCategory.Separation,
    icon: 'SplitSquareVertical',
    parameters: {
      ...feedConditionParams,
      temperature: { label: 'Temperature', unit: '°C', default: 25, min: -273.15, max: 2000, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Vapour', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Liquid', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.Pump]: {
    type: EquipmentType.Pump,
    label: 'Pump',
    category: EquipmentCategory.PressureChange,
    icon: 'CircleDot',
    parameters: {
      ...feedConditionParams,
      outletPressure: { label: 'Outlet Pressure', unit: 'kPa', default: 500, min: 0, max: 100000, type: 'number' },
      efficiency: { label: 'Efficiency', unit: '%', default: 75, min: 0, max: 100, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Inlet', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Outlet', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Compressor]: {
    type: EquipmentType.Compressor,
    label: 'Compressor',
    category: EquipmentCategory.PressureChange,
    icon: 'Gauge',
    parameters: {
      ...feedConditionParams,
      outletPressure: { label: 'Outlet Pressure', unit: 'kPa', default: 500, min: 0, max: 100000, type: 'number' },
      efficiency: { label: 'Adiabatic Efficiency', unit: '%', default: 75, min: 0, max: 100, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Inlet', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Outlet', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.Valve]: {
    type: EquipmentType.Valve,
    label: 'Valve',
    category: EquipmentCategory.PressureChange,
    icon: 'ToggleRight',
    parameters: {
      ...feedConditionParams,
      outletPressure: { label: 'Outlet Pressure', unit: 'kPa', default: 101.325, min: 0, max: 100000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Inlet', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Outlet', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.HeatExchanger]: {
    type: EquipmentType.HeatExchanger,
    label: 'Heat Exchanger',
    category: EquipmentCategory.HeatTransfer,
    icon: 'ArrowLeftRight',
    parameters: {
      ...feedConditionParams,
      hotOutletTemp: { label: 'Hot Outlet Temp', unit: '°C', default: 60, min: -273.15, max: 2000, type: 'number' },
      coldOutletTemp: { label: 'Cold Outlet Temp', unit: '°C', default: 80, min: -273.15, max: 2000, type: 'number' },
      pressureDropHot: { label: 'ΔP Hot Side', unit: 'kPa', default: 10, min: 0, max: 1000, type: 'number' },
      pressureDropCold: { label: 'ΔP Cold Side', unit: 'kPa', default: 10, min: 0, max: 1000, type: 'number' },
    },
    ports: [
      { id: 'in-hot', name: 'Hot Inlet', position: 'left', type: 'inlet' },
      { id: 'in-cold', name: 'Cold Inlet', position: 'left', type: 'inlet' },
      { id: 'out-hot', name: 'Hot Outlet', position: 'right', type: 'outlet' },
      { id: 'out-cold', name: 'Cold Outlet', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.DistillationColumn]: {
    type: EquipmentType.DistillationColumn,
    label: 'Distillation Column',
    category: EquipmentCategory.Separation,
    icon: 'Columns3',
    parameters: {
      ...feedConditionParams,
      numberOfStages: { label: 'Number of Stages', unit: '', default: 10, min: 2, max: 200, type: 'number' },
      feedStage: { label: 'Feed Stage', unit: '', default: 5, min: 1, max: 200, type: 'number' },
      refluxRatio: { label: 'Reflux Ratio', unit: '', default: 1.5, min: 0.01, max: 100, type: 'number' },
      condenserPressure: { label: 'Condenser Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      reboilerDuty: { label: 'Reboiler Duty', unit: 'kW', default: 1000, min: 0, max: 1e8, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Distillate', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Bottoms', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.CSTRReactor]: {
    type: EquipmentType.CSTRReactor,
    label: 'CSTR Reactor',
    category: EquipmentCategory.Reaction,
    icon: 'FlaskConical',
    parameters: {
      ...feedConditionParams,
      volume: { label: 'Volume', unit: 'm³', default: 10, min: 0, max: 10000, type: 'number' },
      temperature: { label: 'Temperature', unit: '°C', default: 80, min: -273.15, max: 2000, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      duty: { label: 'Heat Duty', unit: 'kW', default: 0, min: -1e8, max: 1e8, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.PFRReactor]: {
    type: EquipmentType.PFRReactor,
    label: 'PFR Reactor',
    category: EquipmentCategory.Reaction,
    icon: 'Cylinder',
    parameters: {
      ...feedConditionParams,
      length: { label: 'Length', unit: 'm', default: 5, min: 0, max: 1000, type: 'number' },
      diameter: { label: 'Diameter', unit: 'm', default: 0.5, min: 0, max: 100, type: 'number' },
      temperature: { label: 'Temperature', unit: '°C', default: 80, min: -273.15, max: 2000, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },

  [EquipmentType.ConversionReactor]: {
    type: EquipmentType.ConversionReactor,
    label: 'Conversion Reactor',
    category: EquipmentCategory.Reaction,
    icon: 'FlaskRound',
    parameters: {
      ...feedConditionParams,
      conversion: { label: 'Conversion', unit: '%', default: 80, min: 0, max: 100, type: 'number' },
      temperature: { label: 'Temperature', unit: '°C', default: 80, min: -273.15, max: 2000, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      duty: { label: 'Heat Duty', unit: 'kW', default: 0, min: -1e8, max: 1e8, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },
};

export const equipmentByCategory: Record<EquipmentCategory, EquipmentDefinition[]> = {
  [EquipmentCategory.Mixing]: [
    equipmentLibrary[EquipmentType.Mixer],
    equipmentLibrary[EquipmentType.Splitter],
  ],
  [EquipmentCategory.HeatTransfer]: [
    equipmentLibrary[EquipmentType.Heater],
    equipmentLibrary[EquipmentType.Cooler],
    equipmentLibrary[EquipmentType.HeatExchanger],
  ],
  [EquipmentCategory.Separation]: [
    equipmentLibrary[EquipmentType.Separator],
    equipmentLibrary[EquipmentType.DistillationColumn],
  ],
  [EquipmentCategory.PressureChange]: [
    equipmentLibrary[EquipmentType.Pump],
    equipmentLibrary[EquipmentType.Compressor],
    equipmentLibrary[EquipmentType.Valve],
  ],
  [EquipmentCategory.Reaction]: [
    equipmentLibrary[EquipmentType.CSTRReactor],
    equipmentLibrary[EquipmentType.PFRReactor],
    equipmentLibrary[EquipmentType.ConversionReactor],
  ],
};

export function getDefaultParameters(type: EquipmentType): Record<string, number | string | boolean> {
  const def = equipmentLibrary[type];
  const params: Record<string, number | string | boolean> = {};
  for (const [key, paramDef] of Object.entries(def.parameters)) {
    params[key] = paramDef.default;
  }
  return params;
}
