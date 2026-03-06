#!/usr/bin/env python3
"""Test all 15 AI flowsheet prompts via the agent chat + simulation pipeline."""

import json
import sys
import time
import requests

BASE_URL = "http://localhost:8000/api"

# Port registry (mirrors backend port_registry.py) for connectivity validation
PORT_REGISTRY = {
    "FeedStream": [("out-1", "outlet", True)],
    "ProductStream": [("in-1", "inlet", True)],
    "Heater": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "Cooler": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "Mixer": [("in-1", "inlet", True), ("in-2", "inlet", True), ("in-3", "inlet", False), ("in-4", "inlet", False), ("out-1", "outlet", True)],
    "Splitter": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Separator": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Pump": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "Compressor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "Valve": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "HeatExchanger": [("in-hot", "inlet", True), ("in-cold", "inlet", True), ("out-hot", "outlet", True), ("out-cold", "outlet", True)],
    "DistillationColumn": [("in-1", "inlet", True), ("in-2", "inlet", False), ("out-1", "outlet", True), ("out-2", "outlet", True), ("out-3", "outlet", False), ("out-4", "outlet", False), ("out-5", "outlet", False)],
    "CSTRReactor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "PFRReactor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "ConversionReactor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "Absorber": [("in-1", "inlet", True), ("in-2", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Stripper": [("in-1", "inlet", True), ("in-2", "inlet", False), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Cyclone": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "ThreePhaseSeparator": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True), ("out-3", "outlet", True)],
    "Crystallizer": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Dryer": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "Filter": [("in-1", "inlet", True), ("out-1", "outlet", True), ("out-2", "outlet", True)],
    "PipeSegment": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "DesignSpec": [],
    "EquilibriumReactor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
    "GibbsReactor": [("in-1", "inlet", True), ("out-1", "outlet", True)],
}


def check_port_connectivity(equipment, connections):
    """Check that all required ports are connected. Returns (unconnected_inlets, unconnected_outlets)."""
    connected_sources = {(c["source_id"], c["source_port"]) for c in connections}
    connected_targets = {(c["target_id"], c["target_port"]) for c in connections}

    unconnected_inlets = []
    unconnected_outlets = []

    for eq in equipment:
        eq_type = eq["type"]
        eq_id = eq["id"]
        eq_name = eq.get("name", eq_id)
        ports = PORT_REGISTRY.get(eq_type, [])

        for port_id, port_type, required in ports:
            if not required:
                continue
            if port_type == "inlet" and eq_type != "FeedStream":
                if (eq_id, port_id) not in connected_targets:
                    unconnected_inlets.append(f"{eq_name} ({eq_type}) port {port_id}")
            elif port_type == "outlet" and eq_type != "ProductStream":
                if (eq_id, port_id) not in connected_sources:
                    unconnected_outlets.append(f"{eq_name} ({eq_type}) port {port_id}")

    return unconnected_inlets, unconnected_outlets

PROMPTS = [
    {
        "id": 1,
        "name": "Three-Phase Separator (Oil-Gas-Water)",
        "property_package": "PengRobinson",
        "prompt": "Build a three-phase oil-gas-water separation system. Feed is a wellhead multiphase stream at 50°C, 3000 kPa, 10 kg/s with composition methane 0.40, ethane 0.05, propane 0.05, n-butane 0.03, n-pentane 0.05, n-hexane 0.07, n-heptane 0.05, n-octane 0.05, n-decane 0.10, water 0.15. The feed enters a three-phase separator. Add a control valve on each outlet (gas, light liquid, heavy liquid) reducing pressure to 1000 kPa. Connect all outlets to product streams.",
        "min_equipment": 6,
        "required_types": ["FeedStream", "ThreePhaseSeparator", "Valve", "ProductStream"],
    },
    {
        "id": 2,
        "name": "Gas Sweetening Unit (Amine Treating)",
        "property_package": "PengRobinson",
        "prompt": "Create an amine gas sweetening unit. Sour gas feed at 40°C, 4000 kPa, 10 kg/s with methane 0.90, carbon dioxide 0.05, hydrogen sulfide 0.03, water 0.02. Lean MEA solvent feed at 40°C, 4000 kPa, 15 kg/s with monoethanolamine 0.112, water 0.888. Both feeds enter an absorber with 10 stages. Sweet gas exits the absorber top. Rich amine exits absorber bottom, passes through a heater to 90°C, then enters a stripper with 8 stages and reboiler duty 5000 kW. Acid gas exits stripper top. Lean amine exits stripper bottom to a cooler at 40°C. Terminate the lean amine at a product stream (in practice it recirculates to the absorber). Connect all streams.",
        "min_equipment": 8,
        "required_types": ["FeedStream", "Absorber", "Heater", "Stripper", "Cooler", "ProductStream"],
    },
    {
        "id": 3,
        "name": "Crude Oil Desalting Process",
        "property_package": "PengRobinson",
        "prompt": "Build a crude oil desalting unit. Crude oil feed at 25°C, 1500 kPa, 20 kg/s with n-hexane 0.15, n-heptane 0.20, n-octane 0.25, n-decane 0.30, water 0.10. Wash water feed at 25°C, 1500 kPa, 2 kg/s of pure water. Mix crude and wash water in a mixer, then heat the mixture in a heater to 130°C. Send the heated mixture to a three-phase separator (desalter). Desalted crude exits as light liquid, brine exits as heavy liquid, any gas exits as vapor. Connect all outlet streams to product streams.",
        "min_equipment": 6,
        "required_types": ["FeedStream", "Mixer", "Heater", "ThreePhaseSeparator", "ProductStream"],
    },
    {
        "id": 4,
        "name": "Natural Gas Dehydration (TEG)",
        "property_package": "PengRobinson",
        "prompt": "Design a TEG dehydration unit. Wet gas feed at 30°C, 5000 kPa, 8 kg/s with methane 0.88, ethane 0.05, propane 0.03, water 0.04. Lean TEG solvent feed at 40°C, 5000 kPa, 3 kg/s with triethylene glycol 0.99, water 0.01. Wet gas and lean TEG enter an absorber (contactor) with 6 stages at 5000 kPa. Dry gas exits absorber top. Rich TEG exits absorber bottom, goes through a heater to 150°C, then enters a stripper (regenerator) with 6 stages and reboiler duty 2000 kW. Water vapor exits stripper top. Lean TEG exits stripper bottom to a cooler at 40°C. Terminate the lean TEG at a product stream (in practice it recirculates). Connect all streams.",
        "min_equipment": 8,
        "required_types": ["FeedStream", "Absorber", "Heater", "Stripper", "Cooler", "ProductStream"],
    },
    {
        "id": 5,
        "name": "Naphtha Stabilization",
        "property_package": "PengRobinson",
        "prompt": "Design a naphtha stabilizer column. Feed is unstabilized naphtha at 60°C, 800 kPa, 5 kg/s with methane 0.05, ethane 0.05, propane 0.10, n-butane 0.15, n-pentane 0.25, n-hexane 0.25, n-heptane 0.15. Preheat the feed in a heater to 120°C. Send to a distillation column with 20 stages, feed stage 10, reflux ratio 2.0, condenserPressure 800 kPa, condenserType partial, lightKey propane, heavyKey n-butane. Light gases exit as distillate, stabilized naphtha exits as bottoms. Connect all streams to product streams.",
        "min_equipment": 4,
        "required_types": ["FeedStream", "Heater", "DistillationColumn", "ProductStream"],
    },
    {
        "id": 6,
        "name": "Condensate Recovery and Fractionation",
        "property_package": "PengRobinson",
        "prompt": "Build a condensate recovery unit. Well fluid feed at 45°C, 4000 kPa, 12 kg/s with methane 0.60, ethane 0.08, propane 0.07, n-butane 0.05, n-pentane 0.08, n-hexane 0.07, water 0.05. Feed enters an inlet separator. Gas from separator top goes to a compressor (outlet pressure 7000 kPa, efficiency 75), then a cooler to 40°C, then a product stream for export gas. Liquid from separator bottom is heated in a heater to 100°C and fed to a distillation column (stabilizer) with 15 stages, feed stage 8, reflux ratio 1.5, condenserPressure 500 kPa, lightKey propane, heavyKey n-butane. Light ends exit as distillate, stabilized condensate exits as bottoms. Connect all streams.",
        "min_equipment": 8,
        "required_types": ["FeedStream", "Separator", "Compressor", "Cooler", "Heater", "DistillationColumn", "ProductStream"],
    },
    {
        "id": 7,
        "name": "Crude Distillation Unit (CDU)",
        "property_package": "PengRobinson",
        "prompt": "Design a simplified atmospheric crude distillation unit. Crude feed at 25°C, 500 kPa, 15 kg/s with n-pentane 0.10, n-hexane 0.15, n-heptane 0.20, n-octane 0.20, n-decane 0.20, n-dodecane 0.10, n-hexadecane 0.05. Heat the crude in a heater (desalter proxy) to 130°C, then a second heater (furnace) to 350°C. Feed the heated crude to a distillation column with 30 stages, feed stage 20, reflux ratio 2.5, condenserPressure 150 kPa, lightKey n-hexane, heavyKey n-heptane, sideDrawStage 10, sideDrawType liquid, sideDrawFlowFraction 0.15, condenserType total. Naphtha exits as distillate, a kerosene-range side draw exits out-3, and residue exits as bottoms. Connect all outlet streams to product streams.",
        "min_equipment": 5,
        "required_types": ["FeedStream", "Heater", "DistillationColumn", "ProductStream"],
    },
    {
        "id": 8,
        "name": "LPG Recovery System",
        "property_package": "PengRobinson",
        "prompt": "Build an LPG recovery system with a deethanizer and depropanizer. NGL feed at 30°C, 2500 kPa, 6 kg/s with methane 0.15, ethane 0.20, propane 0.25, n-butane 0.20, isobutane 0.10, n-pentane 0.10. Feed enters a deethanizer column with 25 stages, feed stage 12, reflux ratio 3.0, condenserPressure 2500 kPa, condenserType partial, lightKey ethane, heavyKey propane. C1-C2 gas exits as distillate. Deethanizer bottoms feed a depropanizer column with 30 stages, feed stage 15, reflux ratio 4.0, condenserPressure 1800 kPa, condenserType total, lightKey propane, heavyKey n-butane. Propane product exits as distillate. C4+ LPG exits as bottoms. Connect all streams to product streams.",
        "min_equipment": 5,
        "required_types": ["FeedStream", "DistillationColumn", "ProductStream"],
    },
    {
        "id": 9,
        "name": "Sour Gas Treatment + Sulfur Recovery",
        "property_package": "PengRobinson",
        "prompt": "Build a sour gas treatment unit with a simplified sulfur recovery step. Sour gas feed at 40°C, 4000 kPa, 10 kg/s with methane 0.85, carbon dioxide 0.05, hydrogen sulfide 0.08, water 0.02. Lean MEA solvent feed at 40°C, 4000 kPa, 20 kg/s with monoethanolamine 0.112, water 0.888. Both feeds enter an absorber with 12 stages. Sweet gas exits absorber top. Rich amine goes to a heater to 90°C, then a stripper with 8 stages and reboiler duty 8000 kW. Acid gas from stripper top (rich in H2S) goes to a conversion reactor at 300°C, 200 kPa with 95 percent conversion of hydrogen sulfide as key reactant (representing Claus furnace). Reactor products go through a cooler to 150°C, then a separator. Tail gas exits separator top. Lean amine exits stripper bottom to a cooler at 40°C, then a product stream. Connect all streams.",
        "min_equipment": 10,
        "required_types": ["FeedStream", "Absorber", "Heater", "Stripper", "ConversionReactor", "Cooler", "Separator", "ProductStream"],
    },
    {
        "id": 10,
        "name": "LNG Pre-Treatment Train",
        "property_package": "SRK",
        "prompt": "Design a simplified LNG pre-treatment train. Natural gas feed at 30°C, 6000 kPa, 15 kg/s with methane 0.88, ethane 0.05, propane 0.02, carbon dioxide 0.03, water 0.02. Lean MEA feed at 35°C, 6000 kPa, 10 kg/s with monoethanolamine 0.112, water 0.888. Gas and MEA enter an absorber with 8 stages for CO2 removal. Sweet gas exits absorber top (out-1) to a cooler cooling to 10°C. Rich amine exits absorber bottom (out-2) to a product stream. Cooled gas enters a separator to remove condensed water. Separator vapor goes to a heat exchanger hot side (in-hot). Separator liquid goes to a product stream. Propane refrigerant feed at -30°C, 300 kPa, 20 kg/s pure propane enters the heat exchanger cold side (in-cold). Set heat exchanger hotOutletTemp to -40 and coldOutletTemp to -10. Cold gas exits HX hot side (out-hot) and enters a second separator (LNG flash drum). LNG liquid exits to product stream. Boil-off gas exits to product stream. Propane exits HX cold side (out-cold) to a product stream. Connect ALL outlets.",
        "min_equipment": 10,
        "required_types": ["FeedStream", "Absorber", "Cooler", "Separator", "HeatExchanger", "ProductStream"],
    },
    {
        "id": 11,
        "name": "Offshore Production Train",
        "property_package": "PengRobinson",
        "prompt": "Create an offshore oil and gas production facility. Well fluid feed at 60°C, 5000 kPa, 25 kg/s with methane 0.35, ethane 0.05, propane 0.05, n-butane 0.03, n-pentane 0.05, n-hexane 0.08, n-heptane 0.07, n-octane 0.07, n-decane 0.10, water 0.15. Feed enters a three-phase separator. Gas from separator goes to a compressor (8000 kPa, 75 percent efficiency), then a cooler to 40°C, then a product stream (export gas). Oil (light liquid) goes to a heater (oil treater, 80°C), then a separator (dewatering), then a product stream (export oil). Water from dewatering separator exits to a product stream. Heavy liquid (produced water) from three-phase separator goes to a valve (500 kPa) and a product stream (water disposal). Connect all streams.",
        "min_equipment": 10,
        "required_types": ["FeedStream", "ThreePhaseSeparator", "Compressor", "Separator", "ProductStream"],
    },
    {
        "id": 12,
        "name": "Gas Compression and Export",
        "property_package": "PengRobinson",
        "prompt": "Build a 2-stage gas compression system. Feed at 35°C, 500 kPa, 8 kg/s with methane 0.85, ethane 0.06, propane 0.04, n-butane 0.02, water 0.03. Chain: FeedStream → Inlet Separator. Inlet Sep out-1 (vapor) → Compressor 1 (1500 kPa, 75%). Comp1 out-1 → Cooler 1 (40°C). Cooler1 → KO Drum. KO out-1 (vapor) → Compressor 2 (4500 kPa, 75%). Comp2 → Cooler 2 (40°C). Cooler2 → ProductStream (Export Gas). Inlet Sep out-2 (liquid) → ProductStream. KO out-2 (liquid) → ProductStream.",
        "min_equipment": 8,
        "required_types": ["FeedStream", "Separator", "Compressor", "Cooler", "ProductStream"],
    },
    {
        "id": 13,
        "name": "Hydrocracking Unit",
        "property_package": "SRK",
        "prompt": "Design a simplified hydrocracking unit. Heavy naphtha feed at 50°C, 1000 kPa, 8 kg/s with n-octane 0.40, n-decane 0.50, n-hexane 0.10. Hydrogen makeup feed at 50°C, 10000 kPa, 2 kg/s of pure hydrogen. Mix both feeds in a mixer. Heat the mixture in a heater (reactor furnace) to 400°C. Feed to a conversion reactor at 400°C, 10000 kPa, 70 percent conversion with n-decane as key reactant. Reactor products go through a cooler to 50°C, then a separator (HP separator at 10000 kPa). HP gas exits to a product stream (hydrogen-rich, would recirculate in practice). HP liquid goes through a valve (200 kPa), then a separator (LP separator). LP gas exits to product stream. LP liquid enters a distillation column (fractionator) with 15 stages, feed stage 8, reflux ratio 1.5, condenserPressure 200 kPa, lightKey n-hexane, heavyKey n-octane. Light product exits as distillate, heavy product as bottoms. Connect all streams.",
        "min_equipment": 12,
        "required_types": ["FeedStream", "Mixer", "Heater", "ConversionReactor", "Cooler", "Separator", "Valve", "DistillationColumn", "ProductStream"],
    },
    {
        "id": 14,
        "name": "Randomized Refinery Flow",
        "property_package": "PengRobinson",
        "prompt": "Build a refinery process. Crude feed at 25°C, 300 kPa, 10 kg/s with n-pentane 0.10, n-hexane 0.15, n-heptane 0.25, n-octane 0.25, n-decane 0.25. Chain: Feed → Pump (500 kPa, 75%) → Heater (350°C) → Column (25 stages, feedStage 15, refluxRatio 3, condenserPressure 200, lightKey n-hexane, heavyKey n-heptane). Column out-1 → Cooler (40°C) → ProductStream. Column out-2 → Separator. Separator out-1 → Compressor (800 kPa, 75%) → ProductStream. Separator out-2 → HX in-hot. Water feed 25°C, 300 kPa, 5 kg/s pure water → HX in-cold. HX hotOutletTemp 80, coldOutletTemp 60. HX out-hot → ProductStream. HX out-cold → ProductStream.",
        "min_equipment": 10,
        "required_types": ["FeedStream", "Heater", "DistillationColumn", "Compressor", "Cooler", "Pump", "Separator", "HeatExchanger"],
    },
    {
        "id": 15,
        "name": "Stream-Connectivity Validation",
        "property_package": "PengRobinson",
        "prompt": "Build a gas treatment facility with 2 stages of compression, cooling, and separation. Gas feed at 30°C, 300 kPa, 5 kg/s with methane 0.80, ethane 0.08, propane 0.05, n-butane 0.03, water 0.04. Feed enters inlet separator. Gas from separator goes to Compressor 1 (1000 kPa, 75 percent efficiency), Cooler 1 (35°C), Separator KO-1, Compressor 2 (3000 kPa, 75 percent efficiency), Cooler 2 (35°C), Separator KO-2. Export gas exits KO-2 vapor. Every separator liquid outlet and every final product must connect to a product stream. Ensure zero unconnected ports.",
        "min_equipment": 10,
        "required_types": ["FeedStream", "Separator", "Compressor", "Cooler", "ProductStream"],
    },
]


def test_prompt(prompt_data):
    """Test a single AI prompt: generate flowsheet then simulate."""
    pid = prompt_data["id"]
    name = prompt_data["name"]
    print(f"\n{'='*70}")
    print(f"PROMPT {pid}: {name}")
    print(f"{'='*70}")

    # Step 1: Send to AI
    chat_body = {
        "messages": [{"role": "user", "content": prompt_data["prompt"]}],
        "flowsheet_context": None,
    }

    print(f"  Sending to AI agent...")
    try:
        resp = requests.post(f"{BASE_URL}/agent/chat", json=chat_body, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ AI chat failed: {e}")
        return {"id": pid, "name": name, "status": "AI_ERROR", "error": str(e)}

    data = resp.json()
    action = data.get("flowsheet_action")
    completion_log = data.get("completion_log", [])
    message = data.get("message", {}).get("content", "")[:200]

    if not action:
        print(f"  ❌ No flowsheet_action returned")
        print(f"  AI response: {message}")
        return {"id": pid, "name": name, "status": "NO_ACTION", "error": message}

    equipment = action.get("equipment", [])
    connections = action.get("connections", [])
    eq_types = [e["type"] for e in equipment]

    print(f"  Equipment: {len(equipment)} items, Connections: {len(connections)}")
    print(f"  Types: {', '.join(set(eq_types))}")

    # Show completion log
    if completion_log:
        print(f"  Auto-fixes ({len(completion_log)}):")
        for entry in completion_log[:10]:
            print(f"    - {entry[:120]}")

    # Validate minimum equipment count
    if len(equipment) < prompt_data["min_equipment"]:
        print(f"  ⚠️  Only {len(equipment)} equipment (expected >= {prompt_data['min_equipment']})")

    # Validate required types present
    missing_types = [t for t in prompt_data["required_types"] if t not in eq_types]
    if missing_types:
        print(f"  ⚠️  Missing types: {missing_types}")

    # Check port connectivity
    unconnected_inlets, unconnected_outlets = check_port_connectivity(equipment, connections)
    if unconnected_inlets:
        print(f"  ⚠️  {len(unconnected_inlets)} unconnected required inlet(s):")
        for ui in unconnected_inlets[:5]:
            print(f"    - {ui}")
    if unconnected_outlets:
        print(f"  ⚠️  {len(unconnected_outlets)} unconnected required outlet(s):")
        for uo in unconnected_outlets[:5]:
            print(f"    - {uo}")

    # Step 2: Convert to simulation request format
    # Map equip-N IDs to proper UUIDs for simulation
    import uuid
    id_map = {}
    nodes = []
    for eq in equipment:
        new_id = str(uuid.uuid4())
        id_map[eq["id"]] = new_id
        node = {
            "id": new_id,
            "type": "equipment",
            "position": {"x": 100, "y": 100},
            "data": {
                "equipmentType": eq["type"],
                "name": eq.get("name", eq["type"]),
                "label": eq.get("name", eq["type"]),
                "parameters": eq.get("parameters", {}),
            },
        }
        nodes.append(node)

    edges = []
    for i, conn in enumerate(connections):
        src_id = id_map.get(conn["source_id"])
        tgt_id = id_map.get(conn["target_id"])
        if not src_id or not tgt_id:
            print(f"  ⚠️  Connection references unknown ID: {conn}")
            continue
        edge = {
            "id": f"e{i}",
            "source": src_id,
            "target": tgt_id,
            "sourceHandle": conn["source_port"],
            "targetHandle": conn["target_port"],
            "type": "stream",
        }
        edges.append(edge)

    sim_body = {
        "nodes": nodes,
        "edges": edges,
        "property_package": prompt_data["property_package"],
    }

    print(f"  Running simulation ({prompt_data['property_package']})...")
    try:
        sim_resp = requests.post(f"{BASE_URL}/simulation/run", json=sim_body, timeout=120)
        sim_resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ Simulation request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text[:500]}")
        return {"id": pid, "name": name, "status": "SIM_REQUEST_ERROR", "error": str(e)}

    sim_data = sim_resp.json()
    results = sim_data.get("results", sim_data)

    status = results.get("status", "unknown")
    conv_info = results.get("convergence_info", {})
    converged = conv_info.get("converged", False)
    iterations = conv_info.get("iterations", 0)
    logs = results.get("logs", [])
    eq_results = results.get("equipment_results", {})
    stream_results = results.get("stream_results", {})


    print(f"  Status: {status}, Converged: {converged}, Iterations: {iterations}")

    # Check for warnings/errors in logs
    warnings = [l for l in logs if "WARNING" in l.upper()]
    errors_in_logs = [l for l in logs if "ERROR" in l.upper()]

    if errors_in_logs:
        print(f"  ⚠️  {len(errors_in_logs)} error(s) in logs:")
        for e in errors_in_logs[:5]:
            print(f"    - {e[:120]}")

    if warnings:
        print(f"  ⚠️  {len(warnings)} warning(s) in logs:")
        for w in warnings[:5]:
            print(f"    - {w[:120]}")

    # Check equipment results for errors
    eq_errors = {}
    for eid, eres in eq_results.items():
        if "error" in eres:
            eq_name = eres.get("name", eid[:8])
            eq_errors[eq_name] = eres["error"]
    if eq_errors:
        print(f"  ⚠️  Equipment errors:")
        for en, ee in eq_errors.items():
            print(f"    - {en}: {ee[:100]}")

    # Mass/energy balance
    mb_ok = conv_info.get("mass_balance_ok", None)
    eb_ok = conv_info.get("energy_balance_ok", None)
    if mb_ok is not None:
        print(f"  Mass balance: {'OK' if mb_ok else 'FAIL'}, Energy balance: {'OK' if eb_ok else 'FAIL'}")

    # Stream count
    print(f"  Equipment results: {len(eq_results)}, Stream results: {len(stream_results)}")

    result = {
        "id": pid,
        "name": name,
        "status": status,
        "converged": converged,
        "iterations": iterations,
        "equipment_count": len(equipment),
        "connection_count": len(connections),
        "eq_results_count": len(eq_results),
        "stream_results_count": len(stream_results),
        "warnings": len(warnings),
        "errors": len(errors_in_logs),
        "eq_errors": len(eq_errors),
        "mass_balance_ok": mb_ok,
        "unconnected_inlets": len(unconnected_inlets),
        "unconnected_outlets": len(unconnected_outlets),
        "auto_fixes": len(completion_log) if completion_log else 0,
    }

    if status == "success" and converged and not eq_errors:
        print(f"  ✅ PASS")
    elif status == "success" and not eq_errors:
        print(f"  ⚠️  SUCCESS but not converged (recycle?)")
    else:
        print(f"  ❌ ISSUES DETECTED")

    return result


def main():
    # Check server is running
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
    except Exception:
        print("Backend not reachable at localhost:8000. Start it first.")
        sys.exit(1)

    # Optionally test a single prompt
    if len(sys.argv) > 1:
        prompt_ids = [int(x) for x in sys.argv[1:]]
        prompts_to_test = [p for p in PROMPTS if p["id"] in prompt_ids]
    else:
        prompts_to_test = PROMPTS

    results = []
    for p in prompts_to_test:
        r = test_prompt(p)
        results.append(r)
        time.sleep(1)  # Rate limit buffer

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for r in results if r.get("status") == "success" and r.get("converged") and r.get("eq_errors", 0) == 0)
    partial = sum(1 for r in results if r.get("status") == "success" and not r.get("converged"))
    failed = len(results) - passed - partial
    print(f"  Total: {len(results)}, Passed: {passed}, Partial: {partial}, Failed: {failed}")
    for r in results:
        status_icon = "✅" if r.get("status") == "success" and r.get("converged") and r.get("eq_errors", 0) == 0 else "⚠️" if r.get("status") == "success" else "❌"
        unconn = r.get('unconnected_inlets', 0) + r.get('unconnected_outlets', 0)
        fixes = r.get('auto_fixes', 0)
        print(f"  {status_icon} Prompt {r['id']}: {r['name']} — {r.get('status', '?')} (eq:{r.get('equipment_count','?')}, conn:{r.get('connection_count','?')}, warn:{r.get('warnings','?')}, err:{r.get('eq_errors','?')}, unconn:{unconn}, fixes:{fixes})")


if __name__ == "__main__":
    main()
