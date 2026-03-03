import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Search, Trash2, FlaskConical, Lightbulb } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { searchCompounds } from '../../lib/api-client';
import BIPMatrixEditor from './BIPMatrixEditor';
export default function SimulationBasisPanel({ open, onClose }) {
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const setSimulationBasis = useFlowsheetStore((s) => s.setSimulationBasis);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const setPropertyPackage = useSimulationStore((s) => s.setPropertyPackage);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);
    const [advisor, setAdvisor] = useState(null);
    const searchTimeout = useRef(null);
    const searchContainerRef = useRef(null);
    // Property package advisor — fires when compounds change
    const fetchAdvisor = useCallback(async (compounds) => {
        if (compounds.length === 0) {
            setAdvisor(null);
            return;
        }
        try {
            const res = await fetch('/api/simulation/property-advisor', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ compounds }),
            });
            if (res.ok) {
                const data = await res.json();
                setAdvisor(data);
            }
        }
        catch {
            // silently ignore advisor errors
        }
    }, []);
    useEffect(() => {
        fetchAdvisor(simulationBasis.compounds);
    }, [simulationBasis.compounds, fetchAdvisor]);
    // Debounced compound search
    useEffect(() => {
        if (searchTimeout.current)
            clearTimeout(searchTimeout.current);
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
            }
            catch {
                setSearchResults([]);
            }
            finally {
                setIsSearching(false);
            }
        }, 300);
        return () => {
            if (searchTimeout.current)
                clearTimeout(searchTimeout.current);
        };
    }, [searchQuery]);
    // Close dropdown on outside click
    useEffect(() => {
        const handleClick = (e) => {
            if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
                setShowResults(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);
    const addCompound = (compound) => {
        if (simulationBasis.compounds.includes(compound.name))
            return;
        setSimulationBasis({
            ...simulationBasis,
            compounds: [...simulationBasis.compounds, compound.name],
        });
        setSearchQuery('');
        setShowResults(false);
    };
    const removeCompound = (name) => {
        setSimulationBasis({
            ...simulationBasis,
            compounds: simulationBasis.compounds.filter((c) => c !== name),
        });
    };
    if (!open)
        return null;
    return (_jsxs("div", { className: "absolute right-0 top-0 h-full w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(FlaskConical, { size: 16, className: "text-blue-400" }), _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Simulation Basis" })] }), _jsx("button", { onClick: onClose, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider", children: "Property Package" }), _jsxs("select", { value: propertyPackage, onChange: (e) => setPropertyPackage(e.target.value), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500", children: [_jsx("option", { value: "PengRobinson", children: "Peng-Robinson" }), _jsx("option", { value: "SRK", children: "SRK" }), _jsx("option", { value: "NRTL", children: "NRTL" }), _jsx("option", { value: "UNIQUAC", children: "UNIQUAC" })] })] }), advisor && advisor.recommended !== propertyPackage && (_jsx("div", { className: "bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3", children: _jsxs("div", { className: "flex items-start gap-2", children: [_jsx(Lightbulb, { size: 14, className: "text-blue-500 mt-0.5 flex-shrink-0" }), _jsxs("div", { className: "flex-1", children: [_jsxs("div", { className: "text-xs font-semibold text-blue-700 dark:text-blue-300 mb-1", children: ["Recommended: ", advisor.recommended === 'PengRobinson' ? 'Peng-Robinson' : advisor.recommended] }), _jsx("div", { className: "text-[11px] text-blue-600 dark:text-blue-400 mb-2", children: advisor.reason }), advisor.warnings.length > 0 && (_jsx("div", { className: "text-[10px] text-amber-600 dark:text-amber-400 mb-2", children: advisor.warnings.join(' ') })), _jsxs("button", { onClick: () => setPropertyPackage(advisor.recommended), className: "text-[11px] bg-blue-600 text-white px-2.5 py-1 rounded hover:bg-blue-700 transition-colors", children: ["Apply ", advisor.recommended === 'PengRobinson' ? 'Peng-Robinson' : advisor.recommended] })] })] }) })), _jsxs("div", { children: [_jsxs("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider", children: ["Component List (", simulationBasis.compounds.length, ")"] }), _jsxs("div", { className: "mb-3", ref: searchContainerRef, children: [_jsxs("div", { className: "relative", children: [_jsx(Search, { size: 12, className: "absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" }), _jsx("input", { type: "text", value: searchQuery, onChange: (e) => setSearchQuery(e.target.value), placeholder: "Search compounds...", className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded pl-7 pr-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" }), isSearching && (_jsx("div", { className: "absolute right-2.5 top-1/2 -translate-y-1/2", children: _jsx("div", { className: "w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" }) }))] }), showResults && searchResults.length > 0 && (_jsx("div", { className: "mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded max-h-40 overflow-y-auto", children: searchResults.map((compound) => {
                                            const alreadyAdded = simulationBasis.compounds.includes(compound.name);
                                            return (_jsxs("button", { onClick: () => addCompound(compound), disabled: alreadyAdded, className: `w-full text-left px-3 py-1.5 text-xs hover:bg-gray-200 dark:hover:bg-gray-700 flex items-center justify-between ${alreadyAdded
                                                    ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                                                    : 'text-gray-700 dark:text-gray-300'}`, children: [_jsx("span", { children: compound.name }), _jsx("span", { className: "text-gray-500", children: compound.formula })] }, compound.cas || compound.name));
                                        }) }))] }), simulationBasis.compounds.length > 0 ? (_jsx("div", { className: "space-y-1", children: simulationBasis.compounds.map((name, i) => (_jsxs("div", { className: "flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800/50 rounded border border-gray-200 dark:border-gray-700", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-xs text-gray-400 w-4", children: i + 1 }), _jsx("span", { className: "text-sm text-gray-700 dark:text-gray-300", children: name })] }), _jsx("button", { onClick: () => removeCompound(name), className: "p-0.5 text-gray-400 hover:text-red-400 transition-colors", children: _jsx(Trash2, { size: 12 }) })] }, name))) })) : (_jsx("div", { className: "text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center", children: "No compounds added. Search above to add compounds to the global component list." }))] }), _jsx(BIPMatrixEditor, {})] })] }));
}
