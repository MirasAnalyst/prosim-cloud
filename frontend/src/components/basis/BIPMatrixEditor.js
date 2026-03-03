import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { API_BASE } from '../../lib/api-client';
export default function BIPMatrixEditor() {
    const [expanded, setExpanded] = useState(false);
    const [loading, setLoading] = useState(false);
    const [bipData, setBipData] = useState(null);
    const [error, setError] = useState('');
    const compounds = useFlowsheetStore((s) => s.simulationBasis.compounds);
    const bipOverrides = useFlowsheetStore((s) => s.simulationBasis.bip_overrides);
    const setSimulationBasis = useFlowsheetStore((s) => s.setSimulationBasis);
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    // Fetch BIP matrix when compounds or property package changes
    useEffect(() => {
        if (compounds.length < 2 || !expanded)
            return;
        const fetchBIPs = async () => {
            setLoading(true);
            setError('');
            try {
                const res = await fetch(`${API_BASE}/api/simulation/bip/matrix`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        compounds,
                        property_package: propertyPackage,
                    }),
                });
                if (!res.ok)
                    throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                setBipData(data);
            }
            catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to fetch BIPs');
            }
            finally {
                setLoading(false);
            }
        };
        fetchBIPs();
    }, [compounds, propertyPackage, expanded]);
    if (compounds.length < 2)
        return null;
    const handleBipChange = (i, j, value) => {
        const numVal = parseFloat(value);
        if (isNaN(numVal))
            return;
        const compA = compounds[i];
        const compB = compounds[j];
        const key = `${compA}|${compB}`;
        const newOverrides = { ...(bipOverrides || {}), [key]: numVal };
        setSimulationBasis({
            ...simulationBasis,
            bip_overrides: newOverrides,
        });
        // Also update the displayed matrix
        if (bipData) {
            const newMatrix = bipData.matrix.map((row) => [...row]);
            newMatrix[i][j] = numVal;
            newMatrix[j][i] = numVal;
            setBipData({ ...bipData, matrix: newMatrix });
        }
    };
    const getDisplayValue = (i, j) => {
        if (!bipData)
            return 0;
        const key = `${compounds[i]}|${compounds[j]}`;
        const reverseKey = `${compounds[j]}|${compounds[i]}`;
        if (bipOverrides?.[key] != null)
            return bipOverrides[key];
        if (bipOverrides?.[reverseKey] != null)
            return bipOverrides[reverseKey];
        return bipData.matrix[i]?.[j] ?? 0;
    };
    const isMissing = (i, j) => {
        if (!bipData)
            return false;
        return bipData.missing_pairs.some((p) => (p.comp_a === compounds[i] && p.comp_b === compounds[j]) ||
            (p.comp_a === compounds[j] && p.comp_b === compounds[i]));
    };
    const isOverridden = (i, j) => {
        if (!bipOverrides)
            return false;
        const key = `${compounds[i]}|${compounds[j]}`;
        const reverseKey = `${compounds[j]}|${compounds[i]}`;
        return key in bipOverrides || reverseKey in bipOverrides;
    };
    // Short compound names for display
    const shortName = (name) => {
        if (name.length <= 6)
            return name;
        return name.slice(0, 5) + '.';
    };
    return (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: [_jsxs("button", { onClick: () => setExpanded(!expanded), className: "flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 hover:text-gray-700 dark:hover:text-gray-300 transition-colors w-full", children: [expanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Binary Interaction Parameters", bipData && bipData.missing_pairs.length > 0 && (_jsxs("span", { className: "ml-auto flex items-center gap-1 text-amber-500 normal-case", children: [_jsx(AlertTriangle, { size: 10 }), bipData.missing_pairs.length, " missing"] }))] }), expanded && (_jsxs("div", { className: "space-y-2", children: [loading && (_jsxs("div", { className: "text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2", children: [_jsx("div", { className: "w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" }), "Loading BIPs..."] })), error && (_jsx("div", { className: "text-xs text-red-500 bg-red-50 dark:bg-red-900/20 rounded p-2", children: error })), bipData && !loading && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "text-[10px] text-gray-500 dark:text-gray-400", children: ["Source: ", bipData.source, " (", bipData.parameter_type, ")"] }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "text-[10px] border-collapse", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { className: "p-1 text-left text-gray-500 dark:text-gray-400" }), compounds.map((c) => (_jsx("th", { className: "p-1 text-center text-gray-500 dark:text-gray-400 font-normal", title: c, children: shortName(c) }, c)))] }) }), _jsx("tbody", { children: compounds.map((rowComp, i) => (_jsxs("tr", { children: [_jsx("td", { className: "p-1 text-gray-500 dark:text-gray-400 font-normal", title: rowComp, children: shortName(rowComp) }), compounds.map((_, j) => {
                                                        if (i === j) {
                                                            return (_jsx("td", { className: "p-0.5", children: _jsx("div", { className: "w-12 h-5 bg-gray-200 dark:bg-gray-700 rounded text-center text-gray-400 leading-5", children: "-" }) }, j));
                                                        }
                                                        if (j < i) {
                                                            // Lower triangle — read-only mirror
                                                            return (_jsx("td", { className: "p-0.5", children: _jsx("div", { className: "w-12 h-5 bg-gray-100 dark:bg-gray-800 rounded text-center text-gray-400 leading-5 font-mono", children: getDisplayValue(i, j).toFixed(4) }) }, j));
                                                        }
                                                        const missing = isMissing(i, j);
                                                        const overridden = isOverridden(i, j);
                                                        return (_jsx("td", { className: "p-0.5", children: _jsx("input", { type: "number", step: "0.001", value: getDisplayValue(i, j), onChange: (e) => handleBipChange(i, j, e.target.value), className: `w-12 h-5 text-center font-mono rounded border text-[10px] px-0.5 ${missing
                                                                    ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-400'
                                                                    : overridden
                                                                        ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-400'
                                                                        : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600'} text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500`, title: `${compounds[i]} / ${compounds[j]}` }) }, j));
                                                    })] }, rowComp))) })] }) }), _jsxs("div", { className: "flex gap-3 text-[10px] text-gray-500 dark:text-gray-400", children: [_jsxs("span", { className: "flex items-center gap-1", children: [_jsx("span", { className: "w-2 h-2 rounded bg-amber-400" }), " Missing"] }), _jsxs("span", { className: "flex items-center gap-1", children: [_jsx("span", { className: "w-2 h-2 rounded bg-blue-400" }), " User Override"] })] }), bipData.missing_pairs.length > 0 && (_jsx("div", { className: "text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded p-2", children: "Missing BIP pairs may affect simulation accuracy. Consider providing custom values." }))] }))] }))] }));
}
