"""AI-powered optimization insights analysis service.

Uses OpenAI tool calling to generate structured, quantified optimization
recommendations from simulation results — the same pattern as openai_agent.py.
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.insights import Insight, InsightsSummary, InsightsResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — teaches optimization *methodology*, not fixed rules
# ---------------------------------------------------------------------------
INSIGHTS_SYSTEM_PROMPT = """\
You are a senior process optimization engineer with 25+ years of experience in \
refining, petrochemicals, gas processing, and chemical manufacturing. You are \
analyzing a chemical process simulation to identify optimization opportunities.

## Your approach

1. **Identify the process**: From the equipment types, compounds, topology, and \
operating conditions, determine what process this is (e.g., amine gas treating, \
crude distillation, ethylene cracking, refrigeration loop, water treatment). \
State this in your first insight's description.

2. **Analyze holistically**: Look at the WHOLE flowsheet — cross-equipment \
interactions, stream paths, pressure profiles, temperature cascades, composition \
changes — not just individual units.

3. **Apply process-specific knowledge**: Every process has different optimization \
levers. A gas sweetening plant needs lean amine loading optimization; a \
distillation train needs reflux and feed tray optimization; a compression system \
needs inter-stage cooling analysis. Apply YOUR chemical engineering expertise to \
this specific process.

4. **Quantify everything**: For each insight, calculate:
   - Annual savings ($/yr) using the provided economic parameters
   - CO2 reduction (tonnes/yr) where applicable
   - CAPEX estimate ($) for modifications
   - Simple payback (years) = CAPEX / annual_savings

## Categories

- **energy**: Heat integration, utility reduction, equipment efficiency, waste \
heat recovery, insulation, steam optimization
- **production**: Throughput bottlenecks, conversion improvements, yield \
enhancement, capacity utilization, product quality
- **emissions**: Carbon footprint, fuel optimization, flare/vent minimization, \
fugitive emissions, renewable integration
- **cost**: Operating cost reduction, equipment right-sizing, utility \
optimization, maintenance savings, chemical consumption

## Priority classification

- **critical**: Safety issue or >$500k/yr savings potential
- **high**: >$100k/yr savings or >500 tCO2e/yr reduction
- **medium**: $10k–100k/yr savings or process improvement
- **low**: <$10k/yr savings, nice-to-have improvements

## Implementation types

- **operational_change**: Adjust setpoints, no capital (payback = 0)
- **minor_modification**: <$50k CAPEX, piping/instrument changes
- **moderate_project**: $50k–$500k CAPEX, new equipment or upgrades
- **major_project**: >$500k CAPEX, significant plant modification

## Economic parameters

Use the provided utility costs, carbon price, and operating hours to compute \
all financial figures. Convert equipment duties (W) to GJ/hr for utility \
costing: 1 GJ = 1e9 J, 1 kW = 3.6e-3 GJ/hr.

## Output format

Return 3–15 insights depending on flowsheet complexity. Each insight must \
reference specific equipment and explain the engineering reasoning. Order by \
priority (critical first) then by annual savings (largest first).
"""

# ---------------------------------------------------------------------------
# Tool definition — forces structured JSON matching InsightsResult schema
# ---------------------------------------------------------------------------
GENERATE_INSIGHTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_insights",
        "description": "Generate structured optimization insights with quantified impact for a chemical process simulation.",
        "parameters": {
            "type": "object",
            "properties": {
                "insights": {
                    "type": "array",
                    "description": "List of optimization insights, ordered by priority then savings.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Sequential ID: INS-01, INS-02, ..."},
                            "category": {"type": "string", "enum": ["energy", "production", "emissions", "cost"]},
                            "equipment_id": {"type": "string", "description": "ID of the equipment this insight applies to, or null for system-level"},
                            "equipment_name": {"type": "string", "description": "Name of the equipment"},
                            "title": {"type": "string", "description": "One-line headline of the optimization opportunity"},
                            "description": {"type": "string", "description": "Detailed engineering explanation of the opportunity, reasoning, and expected impact"},
                            "current_value": {"type": "number", "description": "Current parameter value (if applicable)"},
                            "suggested_value": {"type": "number", "description": "Recommended new value (if applicable)"},
                            "parameter": {"type": "string", "description": "Parameter key to adjust (if applicable)"},
                            "unit": {"type": "string", "description": "Unit for current/suggested values (e.g., °C, kPa, %)"},
                            "annual_savings_usd": {"type": "number", "description": "Estimated annual savings in $/yr"},
                            "co2_reduction_tpy": {"type": "number", "description": "CO2 equivalent reduction in tonnes/yr"},
                            "capex_estimate_usd": {"type": "number", "description": "Capital cost estimate in $"},
                            "payback_years": {"type": "number", "description": "Simple payback in years (0 for operational changes)"},
                            "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                            "implementation_type": {
                                "type": "string",
                                "enum": ["operational_change", "minor_modification", "moderate_project", "major_project"],
                            },
                        },
                        "required": ["id", "category", "title", "description", "annual_savings_usd", "priority", "implementation_type"],
                    },
                },
                "summary": {
                    "type": "object",
                    "description": "Summary statistics for all insights.",
                    "properties": {
                        "total_annual_savings": {"type": "number"},
                        "total_co2_reduction": {"type": "number"},
                        "insight_count": {"type": "integer"},
                        "top_quick_wins": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Titles of top 3 insights by shortest payback",
                        },
                        "top_high_impact": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Titles of top 3 insights by largest annual savings",
                        },
                    },
                    "required": ["total_annual_savings", "total_co2_reduction", "insight_count", "top_quick_wins", "top_high_impact"],
                },
            },
            "required": ["insights", "summary"],
        },
    },
}


# ---------------------------------------------------------------------------
# Context builder — formats simulation data for the AI
# ---------------------------------------------------------------------------
def _build_simulation_context(
    simulation_results: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    economic_params: dict[str, Any],
) -> str:
    """Format full simulation data into a text block for the AI prompt."""
    parts: list[str] = []

    # Economic parameters
    parts.append("## Economic Parameters")
    for k, v in economic_params.items():
        label = k.replace("_", " ").title()
        parts.append(f"- {label}: {v}")
    parts.append("")

    # Equipment list with parameters
    parts.append("## Equipment")
    for node in nodes:
        nid = node.get("id", "?")
        ntype = node.get("type", node.get("data", {}).get("equipmentType", "?"))
        name = node.get("name", node.get("data", {}).get("name", nid))
        params = node.get("parameters", node.get("data", {}).get("parameters", {}))
        parts.append(f"- [{nid}] {name} ({ntype})")
        if params:
            for pk, pv in params.items():
                parts.append(f"    {pk}: {pv}")
    parts.append("")

    # Topology
    parts.append("## Topology (connections)")
    for edge in edges:
        src = edge.get("source", "?")
        src_h = edge.get("sourceHandle", "")
        tgt = edge.get("target", "?")
        tgt_h = edge.get("targetHandle", "")
        etype = edge.get("type", "stream")
        parts.append(f"- {src}:{src_h} -> {tgt}:{tgt_h} ({etype})")
    parts.append("")

    # Equipment results
    eq_results = simulation_results.get("equipment_results", {})
    if eq_results:
        parts.append("## Equipment Results")
        for eq_id, data in eq_results.items():
            if isinstance(data, dict):
                parts.append(f"### {eq_id}")
                for rk, rv in data.items():
                    if rk == "error":
                        parts.append(f"  ERROR: {rv}")
                    elif isinstance(rv, dict):
                        parts.append(f"  {rk}:")
                        for sk, sv in rv.items():
                            parts.append(f"    {sk}: {sv}")
                    else:
                        parts.append(f"  {rk}: {rv}")
        parts.append("")

    # Stream results
    stream_results = simulation_results.get("stream_results", {})
    if stream_results:
        parts.append("## Stream Results")
        for sid, data in stream_results.items():
            if isinstance(data, dict):
                parts.append(f"- Stream {sid}: T={data.get('temperature', '?')}°C, "
                             f"P={data.get('pressure', '?')} kPa, "
                             f"flow={data.get('mass_flow', data.get('flowRate', '?'))} kg/s, "
                             f"VF={data.get('vapor_fraction', '?')}")
                comp = data.get("composition", {})
                if comp:
                    parts.append(f"  composition: {comp}")
        parts.append("")

    # Convergence info
    conv = simulation_results.get("convergence_info", {})
    if conv:
        parts.append("## Convergence")
        for ck, cv in conv.items():
            parts.append(f"- {ck}: {cv}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def analyze_insights(
    simulation_results: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    property_package: str,
    economic_params: dict[str, Any],
    raw_context: str = "",
) -> dict[str, Any]:
    """Run AI-powered optimization insights analysis.

    Returns a dict matching InsightsResult schema.
    """
    if not settings.OPENAI_API_KEY:
        return InsightsResult(
            status="error",
            error="OpenAI API key not configured. Set OPENAI_API_KEY in environment.",
        ).model_dump()

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Build context
    context = _build_simulation_context(simulation_results, nodes, edges, economic_params)
    user_message = (
        f"Analyze this {property_package} simulation and generate optimization insights.\n\n"
        f"{context}"
    )

    if raw_context:
        user_message += f"\n\n## Additional File Context\n{raw_context}"

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INSIGHTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=16384,
            tools=[GENERATE_INSIGHTS_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_insights"}},
        )
    except Exception as exc:
        logger.error("OpenAI API call failed: %s", exc)
        return InsightsResult(
            status="error",
            error=f"AI analysis failed: {exc}",
        ).model_dump()

    choice = response.choices[0]

    # Parse tool call
    if choice.finish_reason in ("tool_calls", "stop") and choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        if tool_call.function.name == "generate_insights":
            try:
                args = json.loads(tool_call.function.arguments)
                insights = [Insight(**ins) for ins in args.get("insights", [])]
                raw_summary = args.get("summary", {})
                summary = InsightsSummary(
                    total_annual_savings=raw_summary.get("total_annual_savings", 0),
                    total_co2_reduction=raw_summary.get("total_co2_reduction", 0),
                    insight_count=raw_summary.get("insight_count", len(insights)),
                    top_quick_wins=raw_summary.get("top_quick_wins", []),
                    top_high_impact=raw_summary.get("top_high_impact", []),
                )
                return InsightsResult(
                    insights=insights,
                    summary=summary,
                    status="success",
                ).model_dump()
            except Exception as exc:
                logger.warning("Failed to parse insights tool call: %s", exc)
                return InsightsResult(
                    status="error",
                    error=f"Failed to parse AI response: {exc}",
                ).model_dump()

    # Fallback — AI returned text instead of tool call
    text = choice.message.content or "No insights generated."
    logger.warning("AI returned text instead of tool call: %s", text[:200])
    return InsightsResult(
        status="error",
        error=f"AI did not return structured insights. Response: {text[:500]}",
    ).model_dump()
