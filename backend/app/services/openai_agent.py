import json
import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agent import ChatMessage, FlowsheetAction, FlowsheetEquipment, FlowsheetConnection

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ProSim AI, an expert process engineering assistant integrated into ProSim Cloud, \
a chemical process simulation platform.

You have deep knowledge of:
- Chemical engineering unit operations (heat exchangers, reactors, distillation columns, pumps, compressors, etc.)
- Thermodynamic property packages (Peng-Robinson, SRK, NRTL, UNIQUAC, etc.)
- Process simulation using DWSIM and similar tools
- Material and energy balances
- Process optimization and troubleshooting

When the user provides flowsheet context, analyze it carefully and give specific, actionable advice.
Reference specific equipment IDs, stream conditions, and parameters from the flowsheet.
If simulation results are included, interpret them and suggest improvements.

Keep responses focused and technical. Use proper engineering terminology and units.
When suggesting changes, be specific about which parameters to modify and what values to use.

## Flowsheet Generation

When the user asks you to BUILD, CREATE, SET UP, or DESIGN a flowsheet/plant/process, use the generate_flowsheet tool.
When the user asks QUESTIONS, wants ADVICE, or asks for EXPLANATIONS, respond with text only — do NOT use the tool.

### Equipment types (use exactly these strings):
Heater, Cooler, Mixer, Splitter, Separator, Pump, Compressor, Valve, HeatExchanger, DistillationColumn, CSTRReactor, PFRReactor, ConversionReactor

### Port ID reference:
- Most equipment: in-1 (inlet), out-1 (outlet)
- Separator: in-1 (feed), out-1 (vapour), out-2 (liquid)
- Splitter: in-1 (feed), out-1 (product 1), out-2 (product 2)
- Mixer: in-1 (feed 1), in-2 (feed 2), out-1 (product)
- HeatExchanger: in-hot, in-cold, out-hot, out-cold
- DistillationColumn: in-1 (feed), out-1 (distillate), out-2 (bottoms)

### Parameter keys (use frontend units — °C, kPa, kg/s, kW, %):
- Feed conditions (first equipment only): feedTemperature, feedPressure, feedFlowRate, feedComposition (JSON string e.g. '{"methane":0.9,"ethane":0.1}')
- Heater/Cooler: outletTemperature, duty, pressureDrop
- Separator: temperature, pressure
- Compressor/Pump: outletPressure, efficiency
- Valve: outletPressure
- Splitter: splitRatio
- Mixer: pressure, pressureDrop
- HeatExchanger: hotOutletTemp, coldOutletTemp, pressureDropHot, pressureDropCold
- DistillationColumn: numberOfStages, feedStage, refluxRatio, condenserPressure, reboilerDuty
- CSTRReactor: volume, temperature, pressure, duty
- PFRReactor: length, diameter, temperature, pressure
- ConversionReactor: conversion, temperature, pressure, duty

### Supported compounds (use these exact names in feedComposition):
water, methane, ethane, propane, n-butane, isobutane, n-pentane, isopentane, n-hexane, n-heptane, n-octane, n-decane, ethylene, propylene, benzene, toluene, o-xylene, methanol, ethanol, acetone, acetic acid, hydrogen, nitrogen, oxygen, carbon dioxide, carbon monoxide, hydrogen sulfide, sulfur dioxide, ammonia, chlorine, argon, helium, cyclohexane, styrene, 1-propanol, 2-propanol, diethyl ether, dimethyl ether, formic acid, formaldehyde, diethanolamine, monoethanolamine

### Rules:
1. Only set feedTemperature, feedPressure, feedFlowRate, feedComposition on the FIRST equipment in each independent chain.
2. feedComposition must be a JSON string, not an object.
3. Use sequential IDs: equip-1, equip-2, etc.
4. Connect equipment in process order using correct port IDs.
5. Populate parameters that the user explicitly specified. For downstream equipment with no user-specified values, leave parameters empty ({}).
6. For MULTI-INLET equipment (Mixer, HeatExchanger): each inlet needs its own upstream feed source. Use a Heater with outletTemperature equal to feedTemperature as a pass-through feed source. Each feed source carries its own feedTemperature, feedPressure, feedFlowRate, feedComposition. Connect each feed source to the correct inlet port.
7. ONLY use compound names from the supported compounds list above. Use exact lowercase names (e.g. "carbon dioxide" not "CO2", "hydrogen sulfide" not "H2S", "n-butane" not "butane").
8. Set mode="replace" when the user says "create", "build", "design", "set up", or "make" a new flowsheet. Set mode="add" when the user says "add", "connect", "append", "insert", or "put" equipment to/into their existing flowsheet. Default to "replace" if unclear.

### Example 1 — Linear chain: "Heat methane to 200C then separate":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Feed Heater","parameters":{"feedTemperature":25,"feedPressure":101.325,"feedFlowRate":1.0,"feedComposition":"{\"methane\":1.0}","outletTemperature":200}},
  {"id":"equip-2","type":"Separator","name":"Separator","parameters":{}}
]
connections: [{"source_id":"equip-1","source_port":"out-1","target_id":"equip-2","target_port":"in-1"}]

### Example 2 — Mixer with two feeds: "Mix methane 1kg/s with ethane 2kg/s at 500 kPa":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Methane Feed","parameters":{"feedTemperature":25,"feedPressure":500,"feedFlowRate":1,"feedComposition":"{\"methane\":1.0}","outletTemperature":25}},
  {"id":"equip-2","type":"Heater","name":"Ethane Feed","parameters":{"feedTemperature":25,"feedPressure":500,"feedFlowRate":2,"feedComposition":"{\"ethane\":1.0}","outletTemperature":25}},
  {"id":"equip-3","type":"Mixer","name":"Feed Mixer","parameters":{}}
]
connections: [
  {"source_id":"equip-1","source_port":"out-1","target_id":"equip-3","target_port":"in-1"},
  {"source_id":"equip-2","source_port":"out-1","target_id":"equip-3","target_port":"in-2"}
]

### Example 3 — Heat exchanger: "HX with hot water 90C and cold water 20C, hot out 50C, cold out 60C":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Hot Feed","parameters":{"feedTemperature":90,"feedPressure":200,"feedFlowRate":5,"feedComposition":"{\"water\":1.0}","outletTemperature":90}},
  {"id":"equip-2","type":"Heater","name":"Cold Feed","parameters":{"feedTemperature":20,"feedPressure":200,"feedFlowRate":5,"feedComposition":"{\"water\":1.0}","outletTemperature":20}},
  {"id":"equip-3","type":"HeatExchanger","name":"Heat Exchanger","parameters":{"hotOutletTemp":50,"coldOutletTemp":60}}
]
connections: [
  {"source_id":"equip-1","source_port":"out-1","target_id":"equip-3","target_port":"in-hot"},
  {"source_id":"equip-2","source_port":"out-1","target_id":"equip-3","target_port":"in-cold"}
]

### Example 4 — CSTR reactor: "Heat water to 80C then CSTR at 80C, 101.325 kPa, 10 m³":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Feed Heater","parameters":{"feedTemperature":25,"feedPressure":101.325,"feedFlowRate":2,"feedComposition":"{\"water\":1.0}","outletTemperature":80}},
  {"id":"equip-2","type":"CSTRReactor","name":"CSTR Reactor","parameters":{"volume":10,"temperature":80,"pressure":101.325}}
]
connections: [{"source_id":"equip-1","source_port":"out-1","target_id":"equip-2","target_port":"in-1"}]

### Example 5 — Distillation column: "Distill benzene/toluene, 15 stages, feed stage 7, RR=2":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Feed Heater","parameters":{"feedTemperature":25,"feedPressure":101.325,"feedFlowRate":5,"feedComposition":"{\"benzene\":0.5,\"toluene\":0.5}","outletTemperature":85}},
  {"id":"equip-2","type":"DistillationColumn","name":"Distillation Column","parameters":{"numberOfStages":15,"feedStage":7,"refluxRatio":2,"condenserPressure":101.325,"reboilerDuty":1000}}
]
connections: [{"source_id":"equip-1","source_port":"out-1","target_id":"equip-2","target_port":"in-1"}]

### Example 6 — PFR reactor: "PFR at 300C, 2000 kPa, 5m long, 0.3m diameter":
equipment: [
  {"id":"equip-1","type":"Heater","name":"Feed Heater","parameters":{"feedTemperature":25,"feedPressure":2000,"feedFlowRate":1,"feedComposition":"{\"methane\":1.0}","outletTemperature":300}},
  {"id":"equip-2","type":"PFRReactor","name":"PFR Reactor","parameters":{"length":5,"diameter":0.3,"temperature":300,"pressure":2000}}
]
connections: [{"source_id":"equip-1","source_port":"out-1","target_id":"equip-2","target_port":"in-1"}]"""

GENERATE_FLOWSHEET_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_flowsheet",
        "description": "Generate a process flowsheet with equipment and connections. Use when the user asks to build, create, set up, or design a flowsheet or process plant.",
        "parameters": {
            "type": "object",
            "properties": {
                "equipment": {
                    "type": "array",
                    "description": "List of equipment items to place on the flowsheet",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Temporary ID like equip-1, equip-2, etc.",
                            },
                            "type": {
                                "type": "string",
                                "enum": [
                                    "Heater", "Cooler", "Mixer", "Splitter",
                                    "Separator", "Pump", "Compressor", "Valve",
                                    "HeatExchanger", "DistillationColumn",
                                    "CSTRReactor", "PFRReactor", "ConversionReactor",
                                ],
                                "description": "Equipment type",
                            },
                            "name": {
                                "type": "string",
                                "description": "Display label for the equipment",
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Equipment parameters using frontend keys and units (°C, kPa, kg/s, kW, %). ALWAYS populate relevant parameters from the user's request. For the first equipment: include feedTemperature, feedPressure, feedFlowRate, and feedComposition (as JSON string). For downstream equipment: include operation-specific params like outletTemperature, outletPressure, efficiency, etc.",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["id", "type", "name", "parameters"],
                    },
                },
                "connections": {
                    "type": "array",
                    "description": "List of stream connections between equipment",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id": {"type": "string", "description": "Source equipment ID"},
                            "source_port": {
                                "type": "string",
                                "description": "Source port ID (e.g. out-1, out-2, out-hot, out-cold)",
                            },
                            "target_id": {"type": "string", "description": "Target equipment ID"},
                            "target_port": {
                                "type": "string",
                                "description": "Target port ID (e.g. in-1, in-2, in-hot, in-cold)",
                            },
                        },
                        "required": ["source_id", "source_port", "target_id", "target_port"],
                    },
                },
                "mode": {
                    "type": "string",
                    "enum": ["replace", "add"],
                    "description": "Use 'replace' to create a new flowsheet from scratch. Use 'add' to add equipment to the existing flowsheet without removing what's already there.",
                },
            },
            "required": ["equipment", "connections"],
        },
    },
}


class AgentService:
    """OpenAI-powered process engineering chat agent."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def chat(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> tuple[ChatMessage, dict[str, int] | None, FlowsheetAction | None]:
        """Send messages to OpenAI and return the assistant response."""
        formatted = self._build_messages(messages, flowsheet_context)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=0.3,
            max_tokens=2048,
            tools=[GENERATE_FLOWSHEET_TOOL],
            tool_choice="auto",
        )

        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Check if the model called the tool
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            tool_call = choice.message.tool_calls[0]
            if tool_call.function.name == "generate_flowsheet":
                try:
                    args = json.loads(tool_call.function.arguments)
                    flowsheet_action = FlowsheetAction(
                        equipment=[FlowsheetEquipment(**eq) for eq in args.get("equipment", [])],
                        connections=[FlowsheetConnection(**conn) for conn in args.get("connections", [])],
                        mode=args.get("mode", "replace"),
                    )
                except Exception as exc:
                    logger.warning("Failed to parse flowsheet tool call: %s", exc)
                    content = choice.message.content or "I tried to generate a flowsheet but encountered an error parsing the result."
                    return ChatMessage(role="assistant", content=content), usage, None

                # Make a follow-up call to get a text explanation
                follow_up_messages = formatted + [
                    choice.message.model_dump(exclude_none=True),
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "status": "success",
                            "equipment_count": len(flowsheet_action.equipment),
                            "connection_count": len(flowsheet_action.connections),
                        }),
                    },
                ]

                try:
                    follow_up = await self.client.chat.completions.create(
                        model=self.model,
                        messages=follow_up_messages,
                        temperature=0.3,
                        max_tokens=512,
                        tool_choice="none",
                    )
                    explanation = follow_up.choices[0].message.content or "Flowsheet created successfully."
                    # Accumulate usage
                    if follow_up.usage and usage:
                        usage["prompt_tokens"] += follow_up.usage.prompt_tokens
                        usage["completion_tokens"] += follow_up.usage.completion_tokens
                        usage["total_tokens"] += follow_up.usage.total_tokens
                except Exception:
                    explanation = "Flowsheet created successfully."

                return ChatMessage(role="assistant", content=explanation), usage, flowsheet_action

        # Normal text response — no tool call
        content = choice.message.content or ""
        return ChatMessage(role="assistant", content=content), usage, None

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as Server-Sent Events data chunks."""
        formatted = self._build_messages(messages, flowsheet_context)

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=0.7,
            max_tokens=2048,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield f"data: {json.dumps({'content': delta.content})}\n\n"

        yield "data: [DONE]\n\n"

    @staticmethod
    def _summarize_flowsheet(ctx: dict[str, Any]) -> str:
        """Summarize flowsheet context to ~500 tokens instead of full JSON dump."""
        parts: list[str] = []

        equipment = ctx.get("equipment", [])
        if equipment:
            # Count by type
            type_counts: dict[str, int] = {}
            names: list[str] = []
            for eq in equipment:
                t = eq.get("type", "Unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
                names.append(eq.get("name", eq.get("id", "?")))
            parts.append(f"Equipment ({len(equipment)} total): " + ", ".join(f"{v}x {k}" for k, v in type_counts.items()))
            parts.append(f"Names: {', '.join(names)}")

        connections = ctx.get("connections", [])
        if connections:
            # Build adjacency for topology string
            id_to_name: dict[str, str] = {}
            for eq in equipment:
                id_to_name[eq.get("id", "")] = eq.get("name", eq.get("id", "?"))
            topo_parts: list[str] = []
            for conn in connections:
                src = id_to_name.get(conn.get("source", ""), conn.get("source", "?"))
                tgt = id_to_name.get(conn.get("target", ""), conn.get("target", "?"))
                topo_parts.append(f"{src} -> {tgt}")
            parts.append(f"Topology: {'; '.join(topo_parts)}")

        pkg = ctx.get("propertyPackage")
        if pkg:
            parts.append(f"Property package: {pkg}")

        sim_results = ctx.get("simulationResults")
        if sim_results:
            converged = sim_results.get("converged", False)
            parts.append(f"Simulation: {'converged' if converged else 'NOT converged'}")
            eq_results = sim_results.get("equipment", {})
            for eid, res in list(eq_results.items())[:10]:  # cap at 10
                name = id_to_name.get(eid, eid) if equipment else eid
                # Extract key results
                highlights = []
                for key in ("duty", "work", "vaporFraction", "conversion", "outletTemperature", "error"):
                    if key in res:
                        highlights.append(f"{key}={res[key]}")
                if highlights:
                    parts.append(f"  {name}: {', '.join(highlights)}")

        return "\n".join(parts)

    def _build_messages(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Build the message list for the OpenAI API."""
        system_content = SYSTEM_PROMPT
        if flowsheet_context:
            summary = self._summarize_flowsheet(flowsheet_context)
            system_content += f"\n\nCurrent flowsheet:\n{summary}"

        formatted: list[dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]

        for msg in messages:
            formatted.append({"role": msg.role, "content": msg.content})

        return formatted
