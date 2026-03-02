import { useState, useEffect, useRef } from 'react';
import { X, Search, Trash2, FlaskConical } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { searchCompounds, type CompoundResult } from '../../lib/api-client';

interface SimulationBasisPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function SimulationBasisPanel({ open, onClose }: SimulationBasisPanelProps) {
  const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
  const setSimulationBasis = useFlowsheetStore((s) => s.setSimulationBasis);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const setPropertyPackage = useSimulationStore((s) => s.setPropertyPackage);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<CompoundResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);

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
        const results = await searchCompounds(searchQuery);
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

  // Close dropdown on outside click
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
    if (simulationBasis.compounds.includes(compound.name)) return;
    setSimulationBasis({
      ...simulationBasis,
      compounds: [...simulationBasis.compounds, compound.name],
    });
    setSearchQuery('');
    setShowResults(false);
  };

  const removeCompound = (name: string) => {
    setSimulationBasis({
      ...simulationBasis,
      compounds: simulationBasis.compounds.filter((c) => c !== name),
    });
  };

  if (!open) return null;

  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <FlaskConical size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Simulation Basis</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Property Package */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider">
            Property Package
          </label>
          <select
            value={propertyPackage}
            onChange={(e) => setPropertyPackage(e.target.value)}
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
          >
            <option value="PengRobinson">Peng-Robinson</option>
            <option value="SRK">SRK</option>
            <option value="NRTL">NRTL</option>
            <option value="UNIQUAC">UNIQUAC</option>
          </select>
        </div>

        {/* Compound List */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider">
            Component List ({simulationBasis.compounds.length})
          </label>

          {/* Search */}
          <div className="mb-3" ref={searchContainerRef}>
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
              <div className="mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded max-h-40 overflow-y-auto">
                {searchResults.map((compound) => {
                  const alreadyAdded = simulationBasis.compounds.includes(compound.name);
                  return (
                    <button
                      key={compound.cas || compound.name}
                      onClick={() => addCompound(compound)}
                      disabled={alreadyAdded}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-200 dark:hover:bg-gray-700 flex items-center justify-between ${
                        alreadyAdded
                          ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                          : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      <span>{compound.name}</span>
                      <span className="text-gray-500">{compound.formula}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Compound list */}
          {simulationBasis.compounds.length > 0 ? (
            <div className="space-y-1">
              {simulationBasis.compounds.map((name, i) => (
                <div
                  key={name}
                  className="flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800/50 rounded border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-4">{i + 1}</span>
                    <span className="text-sm text-gray-700 dark:text-gray-300">{name}</span>
                  </div>
                  <button
                    onClick={() => removeCompound(name)}
                    className="p-0.5 text-gray-400 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center">
              No compounds added. Search above to add compounds to the global component list.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
