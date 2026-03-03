import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Upload, X, Loader2, Sparkles, FileText, AlertTriangle, ArrowLeft, Sun, Moon, ChevronDown, ChevronRight } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { useThemeStore } from '../stores/themeStore';
import EconomicParamsForm, { DEFAULT_ECONOMIC_PARAMS, type EconomicParams } from '../components/analysis/EconomicParamsForm';
import InsightsResultsView, { type InsightsResult } from '../components/analysis/InsightsResultsView';
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

interface ParsePreview {
  stream_count: number;
  equipment_count: number;
  node_count: number;
  warnings: string[];
  raw_context_preview: string;
  simulation_results: Record<string, any>;
  nodes: Record<string, any>[];
  detected_unit_system?: string;
  detected_property_package?: string | null;
}

export default function InsightsPage() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState<ParsePreview | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState<InsightsResult | null>(null);
  const [error, setError] = useState('');
  const [econParams, setEconParams] = useState<EconomicParams>({ ...DEFAULT_ECONOMIC_PARAMS });
  const [propertyPackage, setPropertyPackage] = useState('PengRobinson');
  const [previewExpanded, setPreviewExpanded] = useState(false);

  // Issue 2 fix: client-side extension check
  const validateExtension = (f: File): boolean => {
    const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      toast.error(`Unsupported file type ".${ext}". Please use CSV, XLSX, or JSON.`);
      return false;
    }
    return true;
  };

  const handleFile = useCallback(async (f: File) => {
    if (!validateExtension(f)) return;
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
      setPreview(data as ParsePreview);
      // Auto-select detected property package
      if (data.detected_property_package) {
        setPropertyPackage(data.detected_property_package);
      }
      if (data.warnings?.length) {
        // Show max 3 toasts to avoid noise (Issue 6 fix)
        data.warnings.slice(0, 3).forEach((w: string) => toast.warning(w));
        if (data.warnings.length > 3) {
          toast.warning(`...and ${data.warnings.length - 3} more warnings (see preview)`);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse file');
      toast.error('Failed to parse file');
    } finally {
      setParsing(false);
    }
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onDragOver = useCallback((e: React.DragEvent) => {
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
      if (f) handleFile(f);
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
    if (!file) return;
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
      } else {
        setResults(data as InsightsResult);
        toast.success(`Generated ${data.summary?.insight_count ?? 0} insights`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      toast.error('Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/80 dark:bg-gray-950/80 backdrop-blur-lg border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-4xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/app" className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
              <ArrowLeft size={16} />
            </Link>
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-amber-500" />
              <h1 className="text-sm font-semibold">Optimization Insights</h1>
            </div>
          </div>
          <button onClick={toggleTheme} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div className="text-center space-y-1">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Upload Simulation Results</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Upload data from Aspen HYSYS, DWSIM, ProSim, or other tools for AI-powered optimization analysis.
          </p>
        </div>

        {/* File Upload Zone */}
        {!file ? (
          <div
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={onBrowse}
            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
              dragOver
                ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/10'
                : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 bg-white dark:bg-gray-900'
            }`}
          >
            <Upload size={32} className="mx-auto text-gray-400 mb-3" />
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Drag & drop a file here, or click to browse
            </div>
            <div className="text-xs text-gray-400 mt-1">CSV, XLSX, or JSON — up to 10 MB</div>
          </div>
        ) : (
          <div className="flex items-center gap-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
            <FileText size={20} className="text-gray-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{file.name}</div>
              <div className="text-xs text-gray-400">{formatSize(file.size)}</div>
            </div>
            {parsing && <Loader2 size={16} className="animate-spin text-amber-500" />}
            <button onClick={removeFile} className="text-gray-400 hover:text-red-500 transition-colors">
              <X size={16} />
            </button>
          </div>
        )}

        {/* Data Preview */}
        {preview && (
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Data Preview</h3>
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-gray-600 dark:text-gray-400">{preview.stream_count} streams</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-gray-600 dark:text-gray-400">{preview.equipment_count} equipment</span>
              </div>
              {preview.detected_unit_system && preview.detected_unit_system !== 'unknown' && (
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-orange-500" />
                  <span className="text-gray-600 dark:text-gray-400">Units: {preview.detected_unit_system}</span>
                </div>
              )}
            </div>

            {/* Warnings */}
            {preview.warnings.length > 0 && (
              <div className="space-y-1">
                {preview.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-yellow-600 dark:text-yellow-400">
                    <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Expandable raw context preview */}
            {preview.raw_context_preview && (
              <div>
                <button
                  onClick={() => setPreviewExpanded(!previewExpanded)}
                  className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  {previewExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  Raw data preview
                </button>
                {previewExpanded && (
                  <pre className="mt-2 bg-gray-50 dark:bg-gray-800 rounded p-3 text-[10px] text-gray-600 dark:text-gray-400 overflow-x-auto max-h-48 overflow-y-auto">
                    {preview.raw_context_preview}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {/* Property Package selector (Issue 27 fix) */}
        {file && (
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400 block mb-1">
              Property Package
              {preview?.detected_property_package && (
                <span className="ml-2 text-[10px] text-gray-400">(auto-detected: {preview.detected_property_package})</span>
              )}
            </label>
            <select
              value={propertyPackage}
              onChange={(e) => setPropertyPackage(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5"
            >
              {PROPERTY_PACKAGES.map((pp) => (
                <option key={pp.value} value={pp.value}>{pp.label}</option>
              ))}
            </select>
          </div>
        )}

        {/* Economic Params */}
        {file && <EconomicParamsForm value={econParams} onChange={setEconParams} defaultCollapsed={false} />}

        {/* Analyze Button */}
        {file && (
          <button
            onClick={analyze}
            disabled={analyzing || parsing}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-500 disabled:opacity-50 transition-colors"
          >
            {analyzing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {analyzing ? 'Analyzing with AI...' : 'Analyze with AI'}
          </button>
        )}

        {/* Error */}
        {error && <div className="text-sm text-red-400 text-center">{error}</div>}

        {/* Results */}
        {results && results.status === 'success' && (
          <InsightsResultsView results={results} />
        )}
      </main>
    </div>
  );
}
