import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
export const CATEGORY_COLORS = {
    energy: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    production: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    emissions: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    cost: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
};
export const PRIORITY_COLORS = {
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    low: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
};
const IMPL_LABELS = {
    operational_change: 'Operational',
    minor_modification: 'Minor Mod',
    moderate_project: 'Moderate Project',
    major_project: 'Major Project',
};
export function formatCurrency(val) {
    if (val >= 1_000_000)
        return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000)
        return `$${(val / 1_000).toFixed(0)}k`;
    return `$${val.toFixed(0)}`;
}
export default function InsightsResultsView({ results }) {
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [priorityFilter, setPriorityFilter] = useState('all');
    const [expandedIds, setExpandedIds] = useState(new Set());
    const toggleExpanded = (id) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id))
                next.delete(id);
            else
                next.add(id);
            return next;
        });
    };
    if (results.status !== 'success')
        return null;
    const filteredInsights = results.insights.filter((ins) => {
        if (categoryFilter !== 'all' && ins.category !== categoryFilter)
            return false;
        if (priorityFilter !== 'all' && ins.priority !== priorityFilter)
            return false;
        return true;
    });
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { className: "bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center", children: [_jsx("div", { className: "text-lg font-bold text-green-600 dark:text-green-400", children: formatCurrency(results.summary.total_annual_savings) }), _jsx("div", { className: "text-[10px] text-green-700 dark:text-green-500", children: "Savings/yr" })] }), _jsxs("div", { className: "bg-teal-50 dark:bg-teal-900/20 rounded-lg p-3 text-center", children: [_jsx("div", { className: "text-lg font-bold text-teal-600 dark:text-teal-400", children: results.summary.total_co2_reduction.toFixed(0) }), _jsx("div", { className: "text-[10px] text-teal-700 dark:text-teal-500", children: "tCO2e/yr" })] }), _jsxs("div", { className: "bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-center", children: [_jsx("div", { className: "text-lg font-bold text-blue-600 dark:text-blue-400", children: results.summary.insight_count }), _jsx("div", { className: "text-[10px] text-blue-700 dark:text-blue-500", children: "Insights" })] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-2", children: [results.summary.top_quick_wins.length > 0 && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-2", children: [_jsx("div", { className: "text-[10px] font-semibold text-gray-500 mb-1", children: "Quick Wins" }), results.summary.top_quick_wins.map((t, i) => (_jsx("div", { className: "text-[10px] text-gray-600 dark:text-gray-400 truncate", children: t }, i)))] })), results.summary.top_high_impact.length > 0 && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-2", children: [_jsx("div", { className: "text-[10px] font-semibold text-gray-500 mb-1", children: "High Impact" }), results.summary.top_high_impact.map((t, i) => (_jsx("div", { className: "text-[10px] text-gray-600 dark:text-gray-400 truncate", children: t }, i)))] }))] }), _jsxs("div", { className: "flex items-center gap-2 flex-wrap", children: [['all', 'energy', 'production', 'emissions', 'cost'].map((cat) => (_jsx("button", { onClick: () => setCategoryFilter(cat), className: `px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${categoryFilter === cat
                            ? 'bg-gray-800 text-white dark:bg-gray-200 dark:text-gray-900'
                            : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}`, children: cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1) }, cat))), _jsxs("select", { value: priorityFilter, onChange: (e) => setPriorityFilter(e.target.value), className: "ml-auto text-[10px] bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1.5 py-0.5", children: [_jsx("option", { value: "all", children: "All Priorities" }), _jsx("option", { value: "critical", children: "Critical" }), _jsx("option", { value: "high", children: "High" }), _jsx("option", { value: "medium", children: "Medium" }), _jsx("option", { value: "low", children: "Low" })] })] }), _jsxs("div", { className: "space-y-2", children: [filteredInsights.map((ins) => {
                        const expanded = expandedIds.has(ins.id);
                        return (_jsxs("div", { className: "border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden", children: [_jsx("button", { onClick: () => toggleExpanded(ins.id), className: "w-full text-left px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800/50", children: _jsxs("div", { className: "flex items-start gap-2", children: [_jsx("div", { className: "mt-0.5", children: expanded ? _jsx(ChevronDown, { size: 12, className: "text-gray-400" }) : _jsx(ChevronRight, { size: 12, className: "text-gray-400" }) }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsxs("div", { className: "flex items-center gap-1.5 flex-wrap mb-1", children: [_jsx("span", { className: `px-1.5 py-0.5 rounded text-[9px] font-medium ${CATEGORY_COLORS[ins.category] ?? CATEGORY_COLORS.cost}`, children: ins.category }), _jsx("span", { className: `px-1.5 py-0.5 rounded text-[9px] font-medium ${PRIORITY_COLORS[ins.priority] ?? PRIORITY_COLORS.medium}`, children: ins.priority }), _jsx("span", { className: "text-[9px] text-gray-400", children: ins.id })] }), _jsx("div", { className: "text-xs font-medium text-gray-800 dark:text-gray-200 leading-tight", children: ins.title }), _jsxs("div", { className: "flex items-center gap-3 mt-1 text-[10px] text-gray-500", children: [ins.annual_savings_usd > 0 && (_jsxs("span", { className: "text-green-600 dark:text-green-400 font-medium", children: [formatCurrency(ins.annual_savings_usd), "/yr"] })), ins.co2_reduction_tpy > 0 && (_jsxs("span", { className: "text-teal-600 dark:text-teal-400", children: [ins.co2_reduction_tpy.toFixed(0), " tCO2e/yr"] })), ins.payback_years != null && ins.payback_years >= 0 && (_jsx("span", { children: ins.payback_years === 0 ? 'Immediate' : `${ins.payback_years.toFixed(1)} yr payback` }))] }), ins.equipment_name && (_jsx("div", { className: "text-[10px] text-gray-400 mt-0.5", children: ins.equipment_name }))] })] }) }), expanded && (_jsxs("div", { className: "px-3 pb-3 pt-1 border-t border-gray-100 dark:border-gray-800 space-y-2", children: [_jsx("p", { className: "text-[11px] text-gray-600 dark:text-gray-400 leading-relaxed whitespace-pre-wrap", children: ins.description }), ins.parameter && (_jsxs("div", { className: "flex items-center gap-2 text-[10px]", children: [_jsx("span", { className: "text-gray-500", children: "Parameter:" }), _jsx("code", { className: "bg-gray-100 dark:bg-gray-800 px-1 rounded text-gray-700 dark:text-gray-300", children: ins.parameter }), ins.current_value != null && ins.suggested_value != null && (_jsxs("span", { className: "text-gray-500", children: [ins.current_value, " \u2192 ", _jsx("span", { className: "text-green-600 dark:text-green-400 font-medium", children: ins.suggested_value }), ins.unit && ` ${ins.unit}`] }))] })), _jsxs("div", { className: "flex items-center gap-3 text-[10px]", children: [ins.capex_estimate_usd > 0 && (_jsxs("span", { className: "text-gray-500", children: ["CAPEX: ", formatCurrency(ins.capex_estimate_usd)] })), _jsx("span", { className: `px-1.5 py-0.5 rounded text-[9px] ${ins.implementation_type === 'operational_change'
                                                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                                        : ins.implementation_type === 'minor_modification'
                                                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                                                            : ins.implementation_type === 'moderate_project'
                                                                ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                                                                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`, children: IMPL_LABELS[ins.implementation_type] ?? ins.implementation_type })] })] }))] }, ins.id));
                    }), filteredInsights.length === 0 && results.insights.length > 0 && (_jsx("div", { className: "text-xs text-gray-400 text-center py-4", children: "No insights match the current filters." }))] }), _jsx("div", { className: "text-[10px] text-gray-400 text-center italic", children: "AI-generated insights \u2014 verify recommendations before implementation." })] }));
}
