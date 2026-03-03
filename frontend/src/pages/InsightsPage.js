import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Upload, X, Loader2, Sparkles, FileText, AlertTriangle, ArrowLeft, Sun, Moon, ChevronDown, ChevronRight } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { useThemeStore } from '../stores/themeStore';
import EconomicParamsForm, { DEFAULT_ECONOMIC_PARAMS } from '../components/analysis/EconomicParamsForm';
import InsightsResultsView from '../components/analysis/InsightsResultsView';
import { parseInsightsFile, runInsightsFromFile } from '../lib/api-client';
const ACCEPTED_EXTENSIONS = ['csv', 'xlsx', 'xls', 'json'];
const ACCEPTED_TYPES = '.csv,.xlsx,.xls,.json';
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
const PROPERTY_PACKAGES = [
    { value: 'PengRobinson', label: 'Peng-Robinson' },
    { value: 'SRK', label: 'SRK' },
    { value: 'NRTL', label: 'NRTL' },
    { value: 'UNIQUAC', label: 'UNIQUAC' },
];
export default function InsightsPage() {
    const theme = useThemeStore((s) => s.theme);
    const toggleTheme = useThemeStore((s) => s.toggleTheme);
    useEffect(() => {
        document.documentElement.classList.toggle('dark', theme === 'dark');
    }, [theme]);
    const [file, setFile] = useState(null);
    const [dragOver, setDragOver] = useState(false);
    const [parsing, setParsing] = useState(false);
    const [preview, setPreview] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const [econParams, setEconParams] = useState({ ...DEFAULT_ECONOMIC_PARAMS });
    const [propertyPackage, setPropertyPackage] = useState('PengRobinson');
    const [previewExpanded, setPreviewExpanded] = useState(false);
    // Issue 2 fix: client-side extension check
    const validateExtension = (f) => {
        const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
        if (!ACCEPTED_EXTENSIONS.includes(ext)) {
            toast.error(`Unsupported file type ".${ext}". Please use CSV, XLSX, or JSON.`);
            return false;
        }
        return true;
    };
    const handleFile = useCallback(async (f) => {
        if (!validateExtension(f))
            return;
        if (f.size > MAX_SIZE) {
            toast.error('File exceeds 10 MB limit.');
            return;
        }
        setFile(f);
        setResults(null);
        setError('');
        setParsing(true);
        setPreview(null);
        try {
            const data = await parseInsightsFile(f);
            setPreview(data);
            // Auto-select detected property package
            if (data.detected_property_package) {
                setPropertyPackage(data.detected_property_package);
            }
            if (data.warnings?.length) {
                // Show max 3 toasts to avoid noise (Issue 6 fix)
                data.warnings.slice(0, 3).forEach((w) => toast.warning(w));
                if (data.warnings.length > 3) {
                    toast.warning(`...and ${data.warnings.length - 3} more warnings (see preview)`);
                }
            }
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to parse file');
            toast.error('Failed to parse file');
        }
        finally {
            setParsing(false);
        }
    }, []);
    const onDrop = useCallback((e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files[0];
        if (f)
            handleFile(f);
    }, [handleFile]);
    const onDragOver = useCallback((e) => {
        e.preventDefault();
        setDragOver(true);
    }, []);
    const onDragLeave = useCallback(() => setDragOver(false), []);
    const onBrowse = useCallback(() => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = ACCEPTED_TYPES;
        input.onchange = () => {
            const f = input.files?.[0];
            if (f)
                handleFile(f);
        };
        input.click();
    }, [handleFile]);
    const removeFile = () => {
        setFile(null);
        setPreview(null);
        setResults(null);
        setError('');
        setPropertyPackage('PengRobinson');
    };
    const analyze = async () => {
        if (!file)
            return;
        setAnalyzing(true);
        setError('');
        setResults(null);
        try {
            const data = await runInsightsFromFile(file, {
                steam_cost: econParams.steamCost,
                cooling_water_cost: econParams.cwCost,
                electricity_cost: econParams.elecCost,
                fuel_gas_cost: econParams.fuelCost,
                carbon_price: econParams.carbonPrice,
                hours_per_year: econParams.hoursPerYear,
            }, propertyPackage);
            if (data.status === 'error') {
                setError(data.error || 'Analysis failed');
                toast.error('Analysis failed');
            }
            else {
                setResults(data);
                toast.success(`Generated ${data.summary?.insight_count ?? 0} insights`);
            }
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Analysis failed');
            toast.error('Analysis failed');
        }
        finally {
            setAnalyzing(false);
        }
    };
    const formatSize = (bytes) => {
        if (bytes < 1024)
            return `${bytes} B`;
        if (bytes < 1024 * 1024)
            return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };
    return (_jsxs("div", { className: "min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100", children: [_jsx(Toaster, { position: "top-right", richColors: true }), _jsx("header", { className: "sticky top-0 z-30 bg-white/80 dark:bg-gray-950/80 backdrop-blur-lg border-b border-gray-200 dark:border-gray-800", children: _jsxs("div", { className: "max-w-4xl mx-auto px-4 h-12 flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(Link, { to: "/app", className: "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors", children: _jsx(ArrowLeft, { size: 16 }) }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Sparkles, { size: 16, className: "text-amber-500" }), _jsx("h1", { className: "text-sm font-semibold", children: "Optimization Insights" })] })] }), _jsx("button", { onClick: toggleTheme, className: "p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500", children: theme === 'dark' ? _jsx(Sun, { size: 14 }) : _jsx(Moon, { size: 14 }) })] }) }), _jsxs("main", { className: "max-w-4xl mx-auto px-4 py-8 space-y-6", children: [_jsxs("div", { className: "text-center space-y-1", children: [_jsx("h2", { className: "text-lg font-semibold text-gray-800 dark:text-gray-200", children: "Upload Simulation Results" }), _jsx("p", { className: "text-sm text-gray-500 dark:text-gray-400", children: "Upload data from Aspen HYSYS, DWSIM, ProSim, or other tools for AI-powered optimization analysis." })] }), !file ? (_jsxs("div", { onDrop: onDrop, onDragOver: onDragOver, onDragLeave: onDragLeave, onClick: onBrowse, className: `border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${dragOver
                            ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/10'
                            : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 bg-white dark:bg-gray-900'}`, children: [_jsx(Upload, { size: 32, className: "mx-auto text-gray-400 mb-3" }), _jsx("div", { className: "text-sm font-medium text-gray-700 dark:text-gray-300", children: "Drag & drop a file here, or click to browse" }), _jsx("div", { className: "text-xs text-gray-400 mt-1", children: "CSV, XLSX, or JSON \u2014 up to 10 MB" })] })) : (_jsxs("div", { className: "flex items-center gap-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3", children: [_jsx(FileText, { size: 20, className: "text-gray-400 shrink-0" }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsx("div", { className: "text-sm font-medium text-gray-800 dark:text-gray-200 truncate", children: file.name }), _jsx("div", { className: "text-xs text-gray-400", children: formatSize(file.size) })] }), parsing && _jsx(Loader2, { size: 16, className: "animate-spin text-amber-500" }), _jsx("button", { onClick: removeFile, className: "text-gray-400 hover:text-red-500 transition-colors", children: _jsx(X, { size: 16 }) })] })), preview && (_jsxs("div", { className: "bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-700 dark:text-gray-300", children: "Data Preview" }), _jsxs("div", { className: "flex items-center gap-4 text-xs", children: [_jsxs("div", { className: "flex items-center gap-1.5", children: [_jsx("div", { className: "w-2 h-2 rounded-full bg-blue-500" }), _jsxs("span", { className: "text-gray-600 dark:text-gray-400", children: [preview.stream_count, " streams"] })] }), _jsxs("div", { className: "flex items-center gap-1.5", children: [_jsx("div", { className: "w-2 h-2 rounded-full bg-green-500" }), _jsxs("span", { className: "text-gray-600 dark:text-gray-400", children: [preview.equipment_count, " equipment"] })] }), preview.detected_unit_system && preview.detected_unit_system !== 'unknown' && (_jsxs("div", { className: "flex items-center gap-1.5", children: [_jsx("div", { className: "w-2 h-2 rounded-full bg-orange-500" }), _jsxs("span", { className: "text-gray-600 dark:text-gray-400", children: ["Units: ", preview.detected_unit_system] })] }))] }), preview.warnings.length > 0 && (_jsx("div", { className: "space-y-1", children: preview.warnings.map((w, i) => (_jsxs("div", { className: "flex items-start gap-2 text-xs text-yellow-600 dark:text-yellow-400", children: [_jsx(AlertTriangle, { size: 12, className: "shrink-0 mt-0.5" }), _jsx("span", { children: w })] }, i))) })), preview.raw_context_preview && (_jsxs("div", { children: [_jsxs("button", { onClick: () => setPreviewExpanded(!previewExpanded), className: "flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300", children: [previewExpanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Raw data preview"] }), previewExpanded && (_jsx("pre", { className: "mt-2 bg-gray-50 dark:bg-gray-800 rounded p-3 text-[10px] text-gray-600 dark:text-gray-400 overflow-x-auto max-h-48 overflow-y-auto", children: preview.raw_context_preview }))] }))] })), file && (_jsxs("div", { className: "bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3", children: [_jsxs("label", { className: "text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1", children: ["Property Package", preview?.detected_property_package && (_jsxs("span", { className: "ml-2 text-[10px] text-gray-400", children: ["(auto-detected: ", preview.detected_property_package, ")"] }))] }), _jsx("select", { value: propertyPackage, onChange: (e) => setPropertyPackage(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5", children: PROPERTY_PACKAGES.map((pp) => (_jsx("option", { value: pp.value, children: pp.label }, pp.value))) })] })), file && _jsx(EconomicParamsForm, { value: econParams, onChange: setEconParams, defaultCollapsed: false }), file && (_jsxs("button", { onClick: analyze, disabled: analyzing || parsing, className: "w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-500 disabled:opacity-50 transition-colors", children: [analyzing ? _jsx(Loader2, { size: 16, className: "animate-spin" }) : _jsx(Sparkles, { size: 16 }), analyzing ? 'Analyzing with AI...' : 'Analyze with AI'] })), error && _jsx("div", { className: "text-sm text-red-400 text-center", children: error }), results && results.status === 'success' && (_jsx(InsightsResultsView, { results: results }))] })] }));
}
