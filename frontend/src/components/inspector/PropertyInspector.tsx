import { useState, useEffect, useRef, useCallback } from 'react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useUnitStore } from '../../stores/unitStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { searchCompounds, type CompoundResult } from '../../lib/api-client';
import { EquipmentType, SimulationStatus } from '../../types';
import { X, Search, Trash2, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import DesignSpecInspector from './DesignSpecInspector';

const FEED_PARAM_KEYS = ['feedTemperature', 'feedPressure', 'feedFlowRate'];

export default function PropertyInspector() {
  const selectedNodeId = useFlowsheetStore((s) => s.selectedNodeId);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const updateNodeData = useFlowsheetStore((s) => s.updateNodeData);
  const removeNode = useFlowsheetStore((s) => s.removeNode);
  const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);
  const getUpstreamNodes = useFlowsheetStore((s) => s.getUpstreamNodes);
  const globalCompounds = useFlowsheetStore((s) => s.simulationBasis.compounds);

  const results = useSimulationStore((s) => s.results);
  const simStatus = useSimulationStore((s) => s.status);

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  const def = equipmentLibrary[node.data.equipmentType];
  const upstreamNodes = getUpstreamNodes(node.id);
  const isFeedNode = upstreamNodes.length === 0 || node.data.equipmentType === EquipmentType.FeedStream;
  const isStreamNode = node.data.equipmentType === EquipmentType.FeedStream || node.data.equipmentType === EquipmentType.ProductStream;
  // Filter out feed params from regular display
  const regularParams = Object.entries(def.parameters).filter(
    ([key]) => !FEED_PARAM_KEYS.includes(key)
  );

  return (
    <div className="w-72 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Properties</h2>
        <button
          onClick={() => setSelectedNode(null)}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Name</label>
          <input
            type="text"
            value={node.data.name}
            onChange={(e) => updateNodeData(node.id, { name: e.target.value })}
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Type</label>
          <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5">
            {def.label}
          </div>
        </div>

        {isFeedNode && (
          <FeedConditionsSection
            nodeId={node.id}
            parameters={node.data.parameters}
            paramDefs={def.parameters}
            updateNodeData={updateNodeData}
            globalCompounds={globalCompounds}
          />
        )}

        {node.data.equipmentType === EquipmentType.DesignSpec && (
          <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
            <DesignSpecInspector
              nodeId={node.id}
              parameters={node.data.parameters}
              onParamChange={(key, value) =>
                updateNodeData(node.id, {
                  parameters: { ...node.data.parameters, [key]: value },
                })
              }
            />
          </div>
        )}

        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
            Parameters
          </h3>
          <div className="space-y-3">
            {regularParams.map(([key, paramDef]) => (
              <div key={key}>
                <label className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                  <span>{paramDef.label}</span>
                  {paramDef.unit && (
                    <span className="text-gray-500 dark:text-gray-500">{paramDef.unit}</span>
                  )}
                </label>
                {paramDef.type === 'boolean' ? (
                  <button
                    onClick={() =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: !node.data.parameters[key],
                        },
                      })
                    }
                    className={`w-full text-left px-3 py-1.5 rounded text-sm border ${
                      node.data.parameters[key]
                        ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                        : 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {node.data.parameters[key] ? 'Enabled' : 'Disabled'}
                  </button>
                ) : paramDef.type === 'number' ? (
                  <input
                    type="number"
                    value={node.data.parameters[key] !== undefined ? (node.data.parameters[key] as number) : ''}
                    placeholder="Not set"
                    min={paramDef.min}
                    max={paramDef.max}
                    onChange={(e) =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: e.target.value === '' ? undefined as unknown as number : parseFloat(e.target.value) || 0,
                        },
                      })
                    }
                    onBlur={(e) => {
                      const val = parseFloat(e.target.value);
                      if (isNaN(val)) return;
                      let clamped = val;
                      if (paramDef.min !== undefined) clamped = Math.max(paramDef.min, clamped);
                      if (paramDef.max !== undefined) clamped = Math.min(paramDef.max, clamped);
                      if (clamped !== val) {
                        updateNodeData(node.id, {
                          parameters: { ...node.data.parameters, [key]: clamped },
                        });
                      }
                    }}
                    className={`w-full bg-gray-100 dark:bg-gray-800 border rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500 placeholder-gray-400 dark:placeholder-gray-600 ${
                      (() => {
                        const v = node.data.parameters[key];
                        if (v === undefined || v === '') return 'border-gray-300 dark:border-gray-700';
                        const n = Number(v);
                        if (isNaN(n)) return 'border-gray-300 dark:border-gray-700';
                        if ((paramDef.min !== undefined && n < paramDef.min) || (paramDef.max !== undefined && n > paramDef.max)) return 'border-red-500 ring-1 ring-red-500';
                        return 'border-gray-300 dark:border-gray-700';
                      })()
                    }`}
                  />
                ) : (
                  <input
                    type="text"
                    value={node.data.parameters[key] as string}
                    onChange={(e) =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: e.target.value,
                        },
                      })
                    }
                    className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500"
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Simulation Results for FeedStream/ProductStream */}
        {isStreamNode && simStatus === SimulationStatus.Completed && results && (
          <SimResultsSection nodeId={node.id} equipmentType={node.data.equipmentType} results={results} />
        )}

        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <button
            onClick={() => {
              removeNode(node.id);
              setSelectedNode(null);
            }}
            className="w-full px-3 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded text-sm hover:bg-red-500/20 transition-colors"
          >
            Delete Equipment
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Simulation Results Section for FeedStream/ProductStream ──

function fmt(v: number | undefined | null, decimals = 4): string {
  if (v == null || isNaN(v)) return '-';
  return v.toFixed(decimals);
}

function SimResultsSection({ nodeId, equipmentType, results }: {
  nodeId: string;
  equipmentType: EquipmentType;
  results: import('../../types').SimulationResult;
}) {
  const [compExpanded, setCompExpanded] = useState(false);
  const us = useUnitStore((s) => s.unitSystem);
  const cv = us.fromSI;
  const un = us.units;

  const eqResult = results.equipmentResults[nodeId] as Record<string, unknown> | undefined;
  if (!eqResult) return null;

  // Engine returns camelCase keys: outletTemperature, outletPressure, massFlow, vaporFraction
  // Also has nested inlet_streams/outlet_streams with standard keys
  const streamKey = equipmentType === EquipmentType.FeedStream ? 'outlet_streams' : 'inlet_streams';
  const portKey = equipmentType === EquipmentType.FeedStream ? 'out-1' : 'in-1';
  const nested = (eqResult[streamKey] as Record<string, Record<string, unknown>> | undefined)?.[portKey];

  // Prefer nested stream dict (has standard keys), fall back to top-level camelCase
  const temp = (nested?.temperature ?? eqResult.outletTemperature) as number | undefined;
  const pres = (nested?.pressure ?? eqResult.outletPressure) as number | undefined;
  const flow = (nested?.flowRate ?? eqResult.massFlow) as number | undefined;
  const vf = (nested?.vapor_fraction ?? eqResult.vaporFraction) as number | undefined;
  const enthalpy = (nested?.enthalpy ?? eqResult.enthalpy) as number | undefined;
  const mw = (nested?.molecular_weight ?? eqResult.molecular_weight) as number | undefined;
  const molarFlow = (nested?.molar_flow ?? eqResult.molar_flow) as number | undefined;
  const massFracs = (nested?.mass_fractions ?? eqResult.mass_fractions) as Record<string, number> | undefined;
  const compMolarFlows = (nested?.component_molar_flows ?? eqResult.component_molar_flows) as Record<string, number> | undefined;
  const compMassFlows = (nested?.component_mass_flows ?? eqResult.component_mass_flows) as Record<string, number> | undefined;

  const hasAnyData = temp != null || pres != null || flow != null;
  if (!hasAnyData) return null;

  const hasComponents = compMolarFlows && Object.keys(compMolarFlows).length > 0;

  return (
    <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
      <h3 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-3">
        {equipmentType === EquipmentType.FeedStream ? 'Outlet Conditions' : 'Inlet Conditions'}
      </h3>
      <div className="space-y-1.5">
        {temp != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Temperature</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(cv.temperature(temp), 2)} <span className="text-gray-500 text-[10px]">{un.temperature}</span></span>
          </div>
        )}
        {pres != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Pressure</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(cv.pressure(pres), 2)} <span className="text-gray-500 text-[10px]">{un.pressure}</span></span>
          </div>
        )}
        {flow != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Mass Flow</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(cv.massFlow(flow), 4)} <span className="text-gray-500 text-[10px]">{un.massFlow}</span></span>
          </div>
        )}
        {vf != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Vapor Fraction</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(vf, 4)}</span>
          </div>
        )}
        {enthalpy != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Enthalpy</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(cv.enthalpy(enthalpy), 2)} <span className="text-gray-500 text-[10px]">{un.enthalpy}</span></span>
          </div>
        )}
        {mw != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">MW (mix)</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(mw, 2)} <span className="text-gray-500 text-[10px]">g/mol</span></span>
          </div>
        )}
        {molarFlow != null && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-500 dark:text-gray-400">Molar Flow</span>
            <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(cv.molarFlow(molarFlow), 4)} <span className="text-gray-500 text-[10px]">{un.molarFlow}</span></span>
          </div>
        )}
      </div>

      {/* Component properties expandable */}
      {hasComponents && (
        <div className="mt-3 pt-2 border-t border-gray-100 dark:border-gray-800/50">
          <button
            onClick={() => setCompExpanded(!compExpanded)}
            className="flex items-center gap-1 text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2 hover:text-blue-300 transition-colors w-full"
          >
            {compExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            Component Properties
          </button>
          {compExpanded && (
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                    <th className="text-left py-1 pr-1">Component</th>
                    <th className="text-right py-1 px-1">Mass Frac</th>
                    <th className="text-right py-1 px-1">mol/s</th>
                    <th className="text-right py-1 pl-1">kg/s</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(compMolarFlows!).map((name) => (
                    <tr key={name} className="border-b border-gray-100 dark:border-gray-800/50">
                      <td className="py-1 pr-1 text-gray-600 dark:text-gray-400 truncate max-w-[70px]" title={name}>{name}</td>
                      <td className="py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(massFracs?.[name], 4)}</td>
                      <td className="py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(compMolarFlows?.[name], 4)}</td>
                      <td className="py-1 pl-1 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(compMassFlows?.[name], 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Feed Conditions Section ──

interface FeedConditionsSectionProps {
  nodeId: string;
  parameters: Record<string, number | string | boolean>;
  paramDefs: Record<string, { label: string; unit: string; default: number | string | boolean | null; min?: number; max?: number; type: string }>;
  updateNodeData: (id: string, data: { parameters: Record<string, number | string | boolean> }) => void;
  globalCompounds?: string[];
}

function FeedConditionsSection({ nodeId, parameters, paramDefs, updateNodeData, globalCompounds }: FeedConditionsSectionProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<CompoundResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Parse feedComposition from parameters
  const feedComposition: Record<string, number> = (() => {
    const raw = parameters.feedComposition;
    if (!raw) return {};
    if (typeof raw === 'string') {
      try { return JSON.parse(raw); } catch { return {}; }
    }
    if (typeof raw === 'object') return raw as unknown as Record<string, number>;
    return {};
  })();

  const setComposition = useCallback((comp: Record<string, number>) => {
    updateNodeData(nodeId, {
      parameters: {
        ...parameters,
        feedComposition: JSON.stringify(comp),
      },
    });
  }, [nodeId, parameters, updateNodeData]);

  // Debounced compound search
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (searchQuery.length < 2) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    searchTimeout.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        let results = await searchCompounds(searchQuery);
        // Filter by global compound list if defined
        if (globalCompounds && globalCompounds.length > 0) {
          results = results.filter((c) => globalCompounds.includes(c.name));
        }
        setSearchResults(results);
        setShowResults(true);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current);
    };
  }, [searchQuery]);

  // Close search dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as HTMLElement)) {
        setShowResults(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const addCompound = (compound: CompoundResult) => {
    if (feedComposition[compound.name] !== undefined) return;
    const newComp = { ...feedComposition, [compound.name]: 0 };
    setComposition(newComp);
    setSearchQuery('');
    setShowResults(false);
  };

  const removeCompound = (name: string) => {
    const newComp = { ...feedComposition };
    delete newComp[name];
    setComposition(newComp);
  };

  const updateFraction = (name: string, value: number) => {
    setComposition({ ...feedComposition, [name]: value });
  };

  const autoNormalize = () => {
    const entries = Object.entries(feedComposition);
    if (entries.length === 0) return;
    const total = entries.reduce((sum, [, v]) => sum + v, 0);
    if (total === 0) {
      const equal = 1 / entries.length;
      setComposition(Object.fromEntries(entries.map(([k]) => [k, equal])));
    } else {
      setComposition(Object.fromEntries(entries.map(([k, v]) => [k, v / total])));
    }
  };

  const total = Object.values(feedComposition).reduce((s, v) => s + v, 0);

  return (
    <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
      <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-3">
        Feed Conditions
      </h3>

      {/* Feed Temperature, Pressure, Flow Rate */}
      <div className="space-y-3 mb-4">
        {FEED_PARAM_KEYS.map((key) => {
          const paramDef = paramDefs[key];
          if (!paramDef) return null;
          return (
            <div key={key}>
              <label className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                <span>{paramDef.label}</span>
                {paramDef.unit && <span className="text-gray-500">{paramDef.unit}</span>}
              </label>
              <input
                type="number"
                value={parameters[key] as number}
                min={paramDef.min}
                max={paramDef.max}
                onChange={(e) =>
                  updateNodeData(nodeId, {
                    parameters: {
                      ...parameters,
                      [key]: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
          );
        })}
      </div>

      {/* Compound Search */}
      <div className="mb-3" ref={searchContainerRef}>
        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Add Compound</label>
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search compounds..."
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded pl-7 pr-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500"
          />
          {isSearching && (
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
              <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>

        {showResults && searchResults.length > 0 && (
          <div className="mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded max-h-40 overflow-y-auto custom-scrollbar">
            {searchResults.map((compound) => (
              <button
                key={compound.cas || compound.name}
                onClick={() => addCompound(compound)}
                disabled={feedComposition[compound.name] !== undefined}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center justify-between ${
                  feedComposition[compound.name] !== undefined
                    ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                    : 'text-gray-700 dark:text-gray-300'
                }`}
              >
                <span>{compound.name}</span>
                <span className="text-gray-500">{compound.formula}</span>
              </button>
            ))}
          </div>
        )}
        {showResults && searchResults.length === 0 && searchQuery.length >= 2 && !isSearching && (
          <div className="mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-2 text-xs text-gray-500">
            No compounds found
          </div>
        )}
      </div>

      {/* Composition Table */}
      {Object.keys(feedComposition).length > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">Composition (mole fraction)</label>
            <button
              onClick={autoNormalize}
              title="Auto-normalize to 1.0"
              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              <RefreshCw size={10} />
              Normalize
            </button>
          </div>
          <div className="space-y-1.5">
            {Object.entries(feedComposition).map(([name, fraction]) => (
              <div key={name} className="flex items-center gap-1.5">
                <span className="text-xs text-gray-700 dark:text-gray-300 flex-1 truncate" title={name}>
                  {name}
                </span>
                <input
                  type="number"
                  value={fraction}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(e) => updateFraction(name, Math.max(0, parseFloat(e.target.value) || 0))}
                  className="w-20 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-xs text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={() => removeCompound(name)}
                  className="p-0.5 text-gray-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
          <div className={`text-xs mt-1.5 ${Math.abs(total - 1) < 0.001 ? 'text-green-400' : 'text-yellow-400'}`}>
            Total: {total.toFixed(4)}
            {Math.abs(total - 1) >= 0.001 && ' (should be 1.0)'}
          </div>
        </div>
      )}
    </div>
  );
}
