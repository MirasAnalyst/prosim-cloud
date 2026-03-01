"""PDF/text report generator for simulation results."""
import io
from datetime import datetime
from typing import Any


def generate_pdf_report(sim_results: dict[str, Any], project_name: str = "ProSim Cloud") -> bytes:
    """Generate a report from simulation results. Uses reportlab if available, plain text otherwise."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"{project_name} - Simulation Report", styles["Title"]))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 20))

        status = sim_results.get("status", "unknown")
        elements.append(Paragraph(f"Simulation Status: {status}", styles["Heading2"]))

        conv_info = sim_results.get("convergence_info", {})
        if conv_info:
            elements.append(Paragraph(f"Converged: {conv_info.get('converged', 'N/A')}", styles["Normal"]))
            elements.append(Paragraph(f"Iterations: {conv_info.get('iterations', 'N/A')}", styles["Normal"]))
        elements.append(Spacer(1, 15))

        eq_results = sim_results.get("equipment_results", {})
        if eq_results:
            elements.append(Paragraph("Equipment Results", styles["Heading2"]))
            for eq_id, res in eq_results.items():
                if "error" in res:
                    elements.append(Paragraph(f"{eq_id}: ERROR - {res['error']}", styles["Normal"]))
                    continue
                elements.append(Paragraph(eq_id, styles["Heading3"]))
                table_data = [["Parameter", "Value"]]
                for key in ("duty", "work", "outletTemperature", "pressureDrop", "conversion", "vaporFraction"):
                    if key in res:
                        unit = {"duty": "kW", "work": "kW", "outletTemperature": "°C", "pressureDrop": "kPa"}.get(key, "")
                        table_data.append([key, f"{res[key]} {unit}"])
                if "costing" in res:
                    cost = res["costing"].get("purchaseCost", 0)
                    table_data.append(["Equipment Cost", f"${cost:,.0f}"])
                if "sizing" in res:
                    for sk, sv in res["sizing"].items():
                        table_data.append([f"Sizing: {sk}", str(sv)])
                if len(table_data) > 1:
                    t = Table(table_data, colWidths=[200, 200])
                    t.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]))
                    elements.append(t)
                    elements.append(Spacer(1, 10))

        stream_results = sim_results.get("stream_results", {})
        if stream_results:
            elements.append(Paragraph("Stream Results", styles["Heading2"]))
            stream_data = [["Stream", "T (°C)", "P (kPa)", "Flow (kg/s)", "VF"]]
            for sid, sdata in stream_results.items():
                T_C = sdata.get("temperature", 25)
                P_kPa = sdata.get("pressure", 101.325)
                flow = sdata.get("flowRate", 0)
                vf = sdata.get("vapor_fraction", 0)
                stream_data.append([sid, str(round(T_C, 1)), str(round(P_kPa, 1)), str(round(flow, 4)), str(round(vf, 3))])
            if len(stream_data) > 1:
                t = Table(stream_data)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]))
                elements.append(t)

        logs = sim_results.get("logs", [])
        warnings = [l for l in logs if "WARNING" in l or "ERROR" in l]
        if warnings:
            elements.append(Spacer(1, 15))
            elements.append(Paragraph("Warnings & Errors", styles["Heading2"]))
            for w in warnings:
                elements.append(Paragraph(w, styles["Normal"]))

        doc.build(elements)
        return buffer.getvalue()

    except ImportError:
        # Fallback: generate text report
        lines = [
            f"{'=' * 60}",
            f"  {project_name} - Simulation Report",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'=' * 60}",
            "",
            f"Status: {sim_results.get('status', 'unknown')}",
            "",
        ]
        eq_results = sim_results.get("equipment_results", {})
        if eq_results:
            lines.append("EQUIPMENT RESULTS")
            lines.append("-" * 40)
            for eq_id, res in eq_results.items():
                lines.append(f"\n  {eq_id}:")
                for key in ("duty", "work", "outletTemperature", "pressureDrop", "conversion"):
                    if key in res:
                        lines.append(f"    {key}: {res[key]}")
                if "costing" in res:
                    lines.append(f"    Cost: ${res['costing'].get('purchaseCost', 0):,.0f}")
        return "\n".join(lines).encode("utf-8")
