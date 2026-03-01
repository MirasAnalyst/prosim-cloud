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
      temperature: { label: 'Temperature', unit: '°C', default: null, min: -273.15, max: 2000, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: null, min: 0, max: 50000, type: 'number' },
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
      pumpCurve: { label: 'Use Pump Curve', unit: '', default: false, type: 'boolean' },
      ratedFlow: { label: 'Rated Flow', unit: 'm³/h', default: 10, min: 0, max: 10000, type: 'number' },
      ratedHead: { label: 'Rated Head', unit: 'm', default: 50, min: 0, max: 5000, type: 'number' },
      npshAvailable: { label: 'NPSH Available', unit: 'm', default: 10, min: 0, max: 500, type: 'number' },
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
      stages: { label: 'Stages', unit: '', default: 1, min: 1, max: 10, type: 'number' },
      intercoolTemp: { label: 'Intercool Temp', unit: '°C', default: 35, min: -50, max: 200, type: 'number' },
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
      cv: { label: 'Cv', unit: '', default: 0, min: 0, max: 100000, type: 'number' },
      chokedFlowCheck: { label: 'Choked Flow Check', unit: '', default: false, type: 'boolean' },
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
      hotOutletTemp: { label: 'Hot Outlet Temp', unit: '°C', default: null, min: -273.15, max: 2000, type: 'number' },
      coldOutletTemp: { label: 'Cold Outlet Temp', unit: '°C', default: null, min: -273.15, max: 2000, type: 'number' },
      pressureDropHot: { label: 'ΔP Hot Side', unit: 'kPa', default: 10, min: 0, max: 1000, type: 'number' },
      pressureDropCold: { label: 'ΔP Cold Side', unit: 'kPa', default: 10, min: 0, max: 1000, type: 'number' },
      method: { label: 'Method', unit: '', default: 'LMTD', type: 'string' },
      geometry: { label: 'Geometry', unit: '', default: 'shell-tube', type: 'string' },
      foulingFactor: { label: 'Fouling Factor', unit: 'm²K/W', default: 0.0002, min: 0, max: 0.01, type: 'number' },
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
      distillateToFeedRatio: { label: 'D/F Ratio', unit: '', default: 0.5, min: 0.01, max: 0.99, type: 'number' },
      method: { label: 'Method', unit: '', default: 'FUG', type: 'string' },
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
      activationEnergy: { label: 'Activation Energy', unit: 'kJ/mol', default: 0, min: 0, max: 500, type: 'number' },
      preExpFactor: { label: 'Pre-Exp Factor', unit: '1/s', default: 0, min: 0, max: 1e15, type: 'number' },
      jacketUA: { label: 'Jacket UA', unit: 'kW/K', default: 0, min: 0, max: 1000, type: 'number' },
      jacketTemp: { label: 'Jacket Temp', unit: '°C', default: 25, min: -50, max: 500, type: 'number' },
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
      activationEnergy: { label: 'Activation Energy', unit: 'kJ/mol', default: 0, min: 0, max: 500, type: 'number' },
      preExpFactor: { label: 'Pre-Exp Factor', unit: '1/s', default: 0, min: 0, max: 1e15, type: 'number' },
      bedVoidFraction: { label: 'Bed Void Fraction', unit: '', default: 0.4, min: 0.1, max: 0.9, type: 'number' },
      particleDiameter: { label: 'Particle Diameter', unit: 'm', default: 0.003, min: 0.0001, max: 0.1, type: 'number' },
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
      reactionCount: { label: 'Reaction Count', unit: '', default: 1, min: 1, max: 5, type: 'number' },
      reactions: { label: 'Reactions JSON', unit: '', default: '[]', type: 'string' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Product', position: 'right', type: 'outlet' },
    ],
  },
  [EquipmentType.Absorber]: {
    type: EquipmentType.Absorber,
    label: 'Absorber',
    category: EquipmentCategory.Separation,
    icon: 'Columns3',
    parameters: {
      ...feedConditionParams,
      numberOfStages: { label: 'Number of Stages', unit: '', default: 10, min: 2, max: 200, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      temperature: { label: 'Temperature', unit: '°C', default: 25, min: -273.15, max: 2000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Gas Feed', position: 'bottom', type: 'inlet' },
      { id: 'in-2', name: 'Solvent', position: 'top', type: 'inlet' },
      { id: 'out-1', name: 'Lean Gas', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Rich Solvent', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.Stripper]: {
    type: EquipmentType.Stripper,
    label: 'Stripper',
    category: EquipmentCategory.Separation,
    icon: 'Columns3',
    parameters: {
      ...feedConditionParams,
      numberOfStages: { label: 'Number of Stages', unit: '', default: 10, min: 2, max: 200, type: 'number' },
      pressure: { label: 'Pressure', unit: 'kPa', default: 101.325, min: 0, max: 50000, type: 'number' },
      reboilerDuty: { label: 'Reboiler Duty', unit: 'kW', default: 1000, min: 0, max: 1e8, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Rich Solvent', position: 'top', type: 'inlet' },
      { id: 'in-2', name: 'Stripping Gas', position: 'bottom', type: 'inlet' },
      { id: 'out-1', name: 'Overhead Gas', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Lean Solvent', position: 'bottom', type: 'outlet' },
    ],
  },
  [EquipmentType.Cyclone]: {
    type: EquipmentType.Cyclone,
    label: 'Cyclone',
    category: EquipmentCategory.Separation,
    icon: 'Wind',
    parameters: {
      ...feedConditionParams,
      inletDiameter: { label: 'Inlet Diameter', unit: 'm', default: 0.3, min: 0.01, max: 10, type: 'number' },
      pressureDropCoeff: { label: 'ΔP Coefficient K', unit: '', default: 8, min: 1, max: 20, type: 'number' },
      efficiency: { label: 'Separation Efficiency', unit: '%', default: 95, min: 50, max: 99.9, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Clean Gas', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Solids', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.ThreePhaseSeparator]: {
    type: EquipmentType.ThreePhaseSeparator,
    label: 'Three-Phase Separator',
    category: EquipmentCategory.Separation,
    icon: 'Layers',
    parameters: {
      ...feedConditionParams,
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Vapor', position: 'top', type: 'outlet' },
      { id: 'out-2', name: 'Light Liquid', position: 'right', type: 'outlet' },
      { id: 'out-3', name: 'Heavy Liquid', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.Crystallizer]: {
    type: EquipmentType.Crystallizer,
    label: 'Crystallizer',
    category: EquipmentCategory.Separation,
    icon: 'Diamond',
    parameters: {
      ...feedConditionParams,
      crystallizationTemp: { label: 'Crystallization Temp', unit: '°C', default: 5, min: -50, max: 200, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Crystals', position: 'right', type: 'outlet' },
      { id: 'out-2', name: 'Mother Liquor', position: 'bottom', type: 'outlet' },
    ],
  },

  [EquipmentType.Dryer]: {
    type: EquipmentType.Dryer,
    label: 'Dryer',
    category: EquipmentCategory.HeatTransfer,
    icon: 'Flame',
    parameters: {
      ...feedConditionParams,
      outletMoisture: { label: 'Outlet Moisture', unit: '%', default: 5, min: 0, max: 100, type: 'number' },
      duty: { label: 'Duty', unit: 'kW', default: 100, min: 0, max: 10000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Wet Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Dry Product', position: 'right', type: 'outlet' },
      { id: 'out-2', name: 'Vapor', position: 'top', type: 'outlet' },
    ],
  },

  [EquipmentType.Filter]: {
    type: EquipmentType.Filter,
    label: 'Filter',
    category: EquipmentCategory.Separation,
    icon: 'Filter',
    parameters: {
      ...feedConditionParams,
      efficiency: { label: 'Efficiency', unit: '%', default: 95, min: 0, max: 100, type: 'number' },
      pressureDrop: { label: 'Pressure Drop', unit: 'kPa', default: 50, min: 0, max: 1000, type: 'number' },
    },
    ports: [
      { id: 'in-1', name: 'Feed', position: 'left', type: 'inlet' },
      { id: 'out-1', name: 'Filtrate', position: 'right', type: 'outlet' },
      { id: 'out-2', name: 'Cake', position: 'bottom', type: 'outlet' },
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
    equipmentLibrary[EquipmentType.Dryer],
  ],
  [EquipmentCategory.Separation]: [
    equipmentLibrary[EquipmentType.Separator],
    equipmentLibrary[EquipmentType.ThreePhaseSeparator],
    equipmentLibrary[EquipmentType.DistillationColumn],
    equipmentLibrary[EquipmentType.Absorber],
    equipmentLibrary[EquipmentType.Stripper],
    equipmentLibrary[EquipmentType.Cyclone],
    equipmentLibrary[EquipmentType.Crystallizer],
    equipmentLibrary[EquipmentType.Filter],
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
    if (paramDef.default !== null) {
      params[key] = paramDef.default;
    }
  }
  return params;
}
