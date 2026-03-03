import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export interface Insight {
  id: string;
  category: string;
  equipment_id?: string | null;
  equipment_name?: string | null;
  title: string;
  description: string;
  current_value?: number | null;
  suggested_value?: number | null;
  parameter?: string | null;
  unit?: string | null;
  annual_savings_usd: number;
  co2_reduction_tpy: number;
  capex_estimate_usd: number;
  payback_years?: number | null;
  priority: string;
  implementation_type: string;
}

export interface InsightsSummary {
  total_annual_savings: number;
  total_co2_reduction: number;
  insight_count: number;
  top_quick_wins: string[];
  top_high_impact: string[];
}

export interface InsightsResult {
  insights: Insight[];
  summary: InsightsSummary;
  status: string;
  error?: string | null;
}

export const CATEGORY_COLORS: Record<string, string> = {
  energy: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  production: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  emissions: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  cost: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
};

export const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  low: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
};

const IMPL_LABELS: Record<string, string> = {
  operational_change: 'Operational',
  minor_modification: 'Minor Mod',
  moderate_project: 'Moderate Project',
  major_project: 'Major Project',
};

export function formatCurrency(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}k`;
  return `$${val.toFixed(0)}`;
}

interface InsightsResultsViewProps {
  results: InsightsResult;
}

export default function InsightsResultsView({ results }: InsightsResultsViewProps) {
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (results.status !== 'success') return null;

  const filteredInsights = results.insights.filter((ins) => {
    if (categoryFilter !== 'all' && ins.category !== categoryFilter) return false;
    if (priorityFilter !== 'all' && ins.priority !== priorityFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Summary Dashboard */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-green-600 dark:text-green-400">
            {formatCurrency(results.summary.total_annual_savings)}
          </div>
          <div className="text-[10px] text-green-700 dark:text-green-500">Savings/yr</div>
        </div>
        <div className="bg-teal-50 dark:bg-teal-900/20 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-teal-600 dark:text-teal-400">
            {results.summary.total_co2_reduction.toFixed(0)}
          </div>
          <div className="text-[10px] text-teal-700 dark:text-teal-500">tCO2e/yr</div>
        </div>
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-center">
          <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
            {results.summary.insight_count}
          </div>
          <div className="text-[10px] text-blue-700 dark:text-blue-500">Insights</div>
        </div>
      </div>

      {/* Quick Wins & High Impact */}
      <div className="grid grid-cols-2 gap-2">
        {results.summary.top_quick_wins.length > 0 && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-2">
            <div className="text-[10px] font-semibold text-gray-500 mb-1">Quick Wins</div>
            {results.summary.top_quick_wins.map((t, i) => (
              <div key={i} className="text-[10px] text-gray-600 dark:text-gray-400 truncate">{t}</div>
            ))}
          </div>
        )}
        {results.summary.top_high_impact.length > 0 && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-2">
            <div className="text-[10px] font-semibold text-gray-500 mb-1">High Impact</div>
            {results.summary.top_high_impact.map((t, i) => (
              <div key={i} className="text-[10px] text-gray-600 dark:text-gray-400 truncate">{t}</div>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {['all', 'energy', 'production', 'emissions', 'cost'].map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              categoryFilter === cat
                ? 'bg-gray-800 text-white dark:bg-gray-200 dark:text-gray-900'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="ml-auto text-[10px] bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1.5 py-0.5"
        >
          <option value="all">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Insight Cards */}
      <div className="space-y-2">
        {filteredInsights.map((ins) => {
          const expanded = expandedIds.has(ins.id);
          return (
            <div key={ins.id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleExpanded(ins.id)}
                className="w-full text-left px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5">
                    {expanded ? <ChevronDown size={12} className="text-gray-400" /> : <ChevronRight size={12} className="text-gray-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${CATEGORY_COLORS[ins.category] ?? CATEGORY_COLORS.cost}`}>
                        {ins.category}
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${PRIORITY_COLORS[ins.priority] ?? PRIORITY_COLORS.medium}`}>
                        {ins.priority}
                      </span>
                      <span className="text-[9px] text-gray-400">{ins.id}</span>
                    </div>
                    <div className="text-xs font-medium text-gray-800 dark:text-gray-200 leading-tight">{ins.title}</div>
                    <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-500">
                      {ins.annual_savings_usd > 0 && (
                        <span className="text-green-600 dark:text-green-400 font-medium">
                          {formatCurrency(ins.annual_savings_usd)}/yr
                        </span>
                      )}
                      {ins.co2_reduction_tpy > 0 && (
                        <span className="text-teal-600 dark:text-teal-400">
                          {ins.co2_reduction_tpy.toFixed(0)} tCO2e/yr
                        </span>
                      )}
                      {ins.payback_years != null && ins.payback_years >= 0 && (
                        <span>{ins.payback_years === 0 ? 'Immediate' : `${ins.payback_years.toFixed(1)} yr payback`}</span>
                      )}
                    </div>
                    {ins.equipment_name && (
                      <div className="text-[10px] text-gray-400 mt-0.5">{ins.equipment_name}</div>
                    )}
                  </div>
                </div>
              </button>

              {expanded && (
                <div className="px-3 pb-3 pt-1 border-t border-gray-100 dark:border-gray-800 space-y-2">
                  <p className="text-[11px] text-gray-600 dark:text-gray-400 leading-relaxed whitespace-pre-wrap">
                    {ins.description}
                  </p>
                  {ins.parameter && (
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="text-gray-500">Parameter:</span>
                      <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded text-gray-700 dark:text-gray-300">{ins.parameter}</code>
                      {ins.current_value != null && ins.suggested_value != null && (
                        <span className="text-gray-500">
                          {ins.current_value} → <span className="text-green-600 dark:text-green-400 font-medium">{ins.suggested_value}</span>
                          {ins.unit && ` ${ins.unit}`}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-[10px]">
                    {ins.capex_estimate_usd > 0 && (
                      <span className="text-gray-500">CAPEX: {formatCurrency(ins.capex_estimate_usd)}</span>
                    )}
                    <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                      ins.implementation_type === 'operational_change'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : ins.implementation_type === 'minor_modification'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                        : ins.implementation_type === 'moderate_project'
                        ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    }`}>
                      {IMPL_LABELS[ins.implementation_type] ?? ins.implementation_type}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {filteredInsights.length === 0 && results.insights.length > 0 && (
          <div className="text-xs text-gray-400 text-center py-4">No insights match the current filters.</div>
        )}
      </div>

      <div className="text-[10px] text-gray-400 text-center italic">
        AI-generated insights — verify recommendations before implementation.
      </div>
    </div>
  );
}
