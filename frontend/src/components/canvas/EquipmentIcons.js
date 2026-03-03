import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { EquipmentType } from '../../types';
// ViewBox and base sizing data for each equipment shape
const shapeData = {
    [EquipmentType.FeedStream]: { vw: 44, vh: 32, baseSize: 66 },
    [EquipmentType.ProductStream]: { vw: 44, vh: 32, baseSize: 66 },
    [EquipmentType.Mixer]: { vw: 52, vh: 40, baseSize: 78 },
    [EquipmentType.Splitter]: { vw: 52, vh: 40, baseSize: 78 },
    [EquipmentType.Heater]: { vw: 44, vh: 44, baseSize: 66 },
    [EquipmentType.Cooler]: { vw: 44, vh: 44, baseSize: 66 },
    [EquipmentType.HeatExchanger]: { vw: 56, vh: 40, baseSize: 84 },
    [EquipmentType.Separator]: { vw: 36, vh: 60, baseSize: 80 },
    [EquipmentType.Pump]: { vw: 50, vh: 40, baseSize: 75 },
    [EquipmentType.Compressor]: { vw: 44, vh: 44, baseSize: 66 },
    [EquipmentType.Valve]: { vw: 44, vh: 32, baseSize: 66 },
    [EquipmentType.DistillationColumn]: { vw: 36, vh: 76, baseSize: 110 },
    [EquipmentType.CSTRReactor]: { vw: 40, vh: 56, baseSize: 80 },
    [EquipmentType.PFRReactor]: { vw: 60, vh: 32, baseSize: 90 },
    [EquipmentType.ConversionReactor]: { vw: 40, vh: 56, baseSize: 80 },
    [EquipmentType.Absorber]: { vw: 36, vh: 76, baseSize: 110 },
    [EquipmentType.Stripper]: { vw: 36, vh: 76, baseSize: 110 },
    [EquipmentType.Cyclone]: { vw: 40, vh: 60, baseSize: 80 },
    [EquipmentType.ThreePhaseSeparator]: { vw: 56, vh: 40, baseSize: 84 },
    [EquipmentType.Crystallizer]: { vw: 44, vh: 56, baseSize: 80 },
    [EquipmentType.Dryer]: { vw: 52, vh: 40, baseSize: 78 },
    [EquipmentType.Filter]: { vw: 40, vh: 50, baseSize: 75 },
    [EquipmentType.DesignSpec]: { vw: 40, vh: 40, baseSize: 60 },
    [EquipmentType.PipeSegment]: { vw: 60, vh: 24, baseSize: 90 },
    [EquipmentType.EquilibriumReactor]: { vw: 40, vh: 56, baseSize: 80 },
    [EquipmentType.GibbsReactor]: { vw: 40, vh: 56, baseSize: 80 },
};
/** Compute pixel dimensions for the canvas node, preserving aspect ratio. */
export function getNodeDimensions(type) {
    const { vw, vh, baseSize } = shapeData[type];
    if (vw >= vh) {
        return { width: baseSize, height: Math.round(baseSize * vh / vw) };
    }
    return { width: Math.round(baseSize * vw / vh), height: baseSize };
}
/** Compute pixel dimensions for the palette thumbnail. */
export function getPaletteIconDimensions(type) {
    const { vw, vh } = shapeData[type];
    const base = 22;
    if (vw >= vh) {
        return { width: base, height: Math.round(base * vh / vw) };
    }
    return { width: Math.round(base * vw / vh), height: base };
}
// Color constants (HYSYS/DWSIM gray scheme)
const FILL = '#D4D4D8';
const FILL_SEL = '#DBEAFE';
const STROKE = '#71717A';
const STROKE_SEL = '#3B82F6';
const SW = 1.5;
const DETAIL = '#A1A1AA';
const LABEL_CLR = '#52525B';
export function EquipmentIcon({ type, width, height, selected = false }) {
    const fill = selected ? FILL_SEL : FILL;
    const stroke = selected ? STROKE_SEL : STROKE;
    const { vw, vh } = shapeData[type];
    const dims = getNodeDimensions(type);
    const w = width ?? dims.width;
    const h = height ?? dims.height;
    const svgProps = { width: w, height: h, viewBox: `0 0 ${vw} ${vh}` };
    switch (type) {
        // ── Feed Stream: blue arrow-right with "F" ──
        case EquipmentType.FeedStream:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "2,4 30,4 42,16 30,28 2,28", fill: "#BFDBFE", stroke: "#3B82F6", strokeWidth: SW, strokeLinejoin: "round" }), _jsx("text", { x: "18", y: "20", textAnchor: "middle", fill: "#1D4ED8", fontSize: "12", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "F" })] }));
        // ── Product Stream: green arrow-right with "P" ──
        case EquipmentType.ProductStream:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "2,4 30,4 42,16 30,28 2,28", fill: "#BBF7D0", stroke: "#22C55E", strokeWidth: SW, strokeLinejoin: "round" }), _jsx("text", { x: "18", y: "20", textAnchor: "middle", fill: "#166534", fontSize: "12", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "P" })] }));
        // ── Mixer: pentagon arrow pointing right ──
        case EquipmentType.Mixer:
            return (_jsx("svg", { ...svgProps, children: _jsx("polygon", { points: "2,2 34,2 50,20 34,38 2,38", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }) }));
        // ── Splitter: pentagon arrow pointing left ──
        case EquipmentType.Splitter:
            return (_jsx("svg", { ...svgProps, children: _jsx("polygon", { points: "2,20 18,2 50,2 50,38 18,38", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }) }));
        // ── Heater: diamond with "H" ──
        case EquipmentType.Heater:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "22,2 42,22 22,42 2,22", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }), _jsx("text", { x: "22", y: "27", textAnchor: "middle", fill: LABEL_CLR, fontSize: "14", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "H" })] }));
        // ── Cooler: diamond with "C" ──
        case EquipmentType.Cooler:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "22,2 42,22 22,42 2,22", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }), _jsx("text", { x: "22", y: "27", textAnchor: "middle", fill: LABEL_CLR, fontSize: "14", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "C" })] }));
        // ── Heat Exchanger: ellipse with diagonal baffle line ──
        case EquipmentType.HeatExchanger:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("ellipse", { cx: "28", cy: "20", rx: "26", ry: "18", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("line", { x1: "8", y1: "34", x2: "48", y2: "6", stroke: DETAIL, strokeWidth: SW })] }));
        // ── Separator: vertical capsule with liquid level ──
        case EquipmentType.Separator:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "4", width: "28", height: "52", rx: "14", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("line", { x1: "6", y1: "38", x2: "30", y2: "38", stroke: DETAIL, strokeWidth: 1, strokeDasharray: "3,2" })] }));
        // ── Pump: circle body + triangular discharge nozzle ──
        case EquipmentType.Pump:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("circle", { cx: "20", cy: "20", r: "16", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("polygon", { points: "34,10 48,20 34,30", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" })] }));
        // ── Compressor: trapezoid (wide inlet left, narrow outlet right) ──
        case EquipmentType.Compressor:
            return (_jsx("svg", { ...svgProps, children: _jsx("polygon", { points: "2,2 42,10 42,34 2,42", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }) }));
        // ── Valve: bowtie (two triangles meeting at center) ──
        case EquipmentType.Valve:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "2,4 22,16 2,28", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }), _jsx("polygon", { points: "42,4 22,16 42,28", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" })] }));
        // ── Distillation Column: tall rounded rect with tray lines ──
        case EquipmentType.DistillationColumn:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "4", width: "28", height: "68", rx: "6", fill: fill, stroke: stroke, strokeWidth: SW }), [16, 25, 34, 43, 52, 61].map((y) => (_jsx("line", { x1: "8", y1: y, x2: "28", y2: y, stroke: DETAIL, strokeWidth: 0.8 }, y)))] }));
        // ── CSTR Reactor: vertical cylinder with stirrer ──
        case EquipmentType.CSTRReactor:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("path", { d: "M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("ellipse", { cx: "20", cy: "12", rx: "14", ry: "6", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("line", { x1: "20", y1: "6", x2: "20", y2: "38", stroke: DETAIL, strokeWidth: 1.5 }), _jsx("line", { x1: "13", y1: "26", x2: "27", y2: "26", stroke: DETAIL, strokeWidth: 1.5 }), _jsx("line", { x1: "13", y1: "34", x2: "27", y2: "34", stroke: DETAIL, strokeWidth: 1.5 })] }));
        // ── PFR Reactor: horizontal capsule with segment lines ──
        case EquipmentType.PFRReactor:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "4", width: "52", height: "24", rx: "12", fill: fill, stroke: stroke, strokeWidth: SW }), [18, 30, 42].map((x) => (_jsx("line", { x1: x, y1: "6", x2: x, y2: "26", stroke: DETAIL, strokeWidth: 0.8 }, x)))] }));
        // ── Conversion Reactor: vertical cylinder with "C" label ──
        case EquipmentType.ConversionReactor:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("path", { d: "M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("ellipse", { cx: "20", cy: "12", rx: "14", ry: "6", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("text", { x: "20", y: "33", textAnchor: "middle", fill: LABEL_CLR, fontSize: "14", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "C" })] }));
        // ── Cyclone: conical body with tangential inlet ──
        case EquipmentType.Cyclone:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "8", y: "4", width: "24", height: "22", rx: "3", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("polygon", { points: "8,26 32,26 24,56 16,56", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }), _jsx("line", { x1: "20", y1: "4", x2: "20", y2: "12", stroke: DETAIL, strokeWidth: 1.5 }), _jsx("path", { d: "M14,14 C14,10 26,10 26,14 C26,18 14,18 14,14", fill: "none", stroke: DETAIL, strokeWidth: 0.8 })] }));
        // ── Absorber: tall column with "A" label + packing lines ──
        case EquipmentType.Absorber:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "4", width: "28", height: "68", rx: "6", fill: fill, stroke: stroke, strokeWidth: SW }), [20, 30, 40, 50].map((y) => (_jsx("line", { x1: "8", y1: y, x2: "28", y2: y, stroke: DETAIL, strokeWidth: 0.8, strokeDasharray: "2,2" }, y))), _jsx("text", { x: "18", y: "16", textAnchor: "middle", fill: LABEL_CLR, fontSize: "10", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "A" })] }));
        // ── Stripper: tall column with "S" label + packing lines ──
        case EquipmentType.Stripper:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "4", width: "28", height: "68", rx: "6", fill: fill, stroke: stroke, strokeWidth: SW }), [20, 30, 40, 50].map((y) => (_jsx("line", { x1: "8", y1: y, x2: "28", y2: y, stroke: DETAIL, strokeWidth: 0.8, strokeDasharray: "2,2" }, y))), _jsx("text", { x: "18", y: "16", textAnchor: "middle", fill: LABEL_CLR, fontSize: "10", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "S" })] }));
        // ── Three-Phase Separator: horizontal drum with 3 sections ──
        case EquipmentType.ThreePhaseSeparator:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "4", y: "8", width: "48", height: "24", rx: "6", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("line", { x1: "20", y1: "8", x2: "20", y2: "32", stroke: DETAIL, strokeWidth: 0.8, strokeDasharray: "2,2" }), _jsx("line", { x1: "36", y1: "8", x2: "36", y2: "32", stroke: DETAIL, strokeWidth: 0.8, strokeDasharray: "2,2" }), _jsx("text", { x: "12", y: "23", textAnchor: "middle", fill: LABEL_CLR, fontSize: "7", fontFamily: "Arial", children: "V" }), _jsx("text", { x: "28", y: "23", textAnchor: "middle", fill: LABEL_CLR, fontSize: "7", fontFamily: "Arial", children: "L1" }), _jsx("text", { x: "44", y: "23", textAnchor: "middle", fill: LABEL_CLR, fontSize: "7", fontFamily: "Arial", children: "L2" })] }));
        // ── Crystallizer: vessel with crystal shapes ──
        case EquipmentType.Crystallizer:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "6", y: "6", width: "32", height: "40", rx: "4", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("polygon", { points: "18,20 22,14 26,20 22,26", fill: "none", stroke: DETAIL, strokeWidth: 1 }), _jsx("polygon", { points: "14,32 18,26 22,32 18,38", fill: "none", stroke: DETAIL, strokeWidth: 0.8 }), _jsx("text", { x: "22", y: "48", textAnchor: "middle", fill: LABEL_CLR, fontSize: "7", fontFamily: "Arial", children: "CR" })] }));
        // ── Dryer: rectangular box with wavy lines ──
        case EquipmentType.Dryer:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "6", y: "6", width: "40", height: "28", rx: "3", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("path", { d: "M12,16 Q16,12 20,16 Q24,20 28,16 Q32,12 36,16", fill: "none", stroke: DETAIL, strokeWidth: 1 }), _jsx("path", { d: "M12,24 Q16,20 20,24 Q24,28 28,24 Q32,20 36,24", fill: "none", stroke: DETAIL, strokeWidth: 1 })] }));
        // ── Filter: funnel shape ──
        case EquipmentType.Filter:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("polygon", { points: "4,6 36,6 28,30 12,30", fill: fill, stroke: stroke, strokeWidth: SW, strokeLinejoin: "round" }), _jsx("rect", { x: "14", y: "30", width: "12", height: "14", rx: "2", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("line", { x1: "10", y1: "14", x2: "30", y2: "14", stroke: DETAIL, strokeWidth: 0.8 }), _jsx("line", { x1: "12", y1: "20", x2: "28", y2: "20", stroke: DETAIL, strokeWidth: 0.8 })] }));
        // ── Design Spec: crosshair/target ──
        case EquipmentType.DesignSpec:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("circle", { cx: "20", cy: "20", r: "16", fill: "none", stroke: "#8B5CF6", strokeWidth: SW }), _jsx("circle", { cx: "20", cy: "20", r: "10", fill: "none", stroke: "#8B5CF6", strokeWidth: 1 }), _jsx("circle", { cx: "20", cy: "20", r: "4", fill: "#8B5CF6" }), _jsx("line", { x1: "20", y1: "2", x2: "20", y2: "10", stroke: "#8B5CF6", strokeWidth: 1 }), _jsx("line", { x1: "20", y1: "30", x2: "20", y2: "38", stroke: "#8B5CF6", strokeWidth: 1 }), _jsx("line", { x1: "2", y1: "20", x2: "10", y2: "20", stroke: "#8B5CF6", strokeWidth: 1 }), _jsx("line", { x1: "30", y1: "20", x2: "38", y2: "20", stroke: "#8B5CF6", strokeWidth: 1 })] }));
        // ── Pipe Segment: horizontal pipe with flanges ──
        case EquipmentType.PipeSegment:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("rect", { x: "2", y: "6", width: "6", height: "12", rx: "1", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("rect", { x: "8", y: "8", width: "44", height: "8", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("rect", { x: "52", y: "6", width: "6", height: "12", rx: "1", fill: fill, stroke: stroke, strokeWidth: SW })] }));
        // ── Equilibrium Reactor: vertical cylinder with "Eq" label ──
        case EquipmentType.EquilibriumReactor:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("path", { d: "M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("ellipse", { cx: "20", cy: "12", rx: "14", ry: "6", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("text", { x: "20", y: "33", textAnchor: "middle", fill: "#059669", fontSize: "11", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "Eq" })] }));
        // ── Gibbs Reactor: vertical cylinder with "G" label ──
        case EquipmentType.GibbsReactor:
            return (_jsxs("svg", { ...svgProps, children: [_jsx("path", { d: "M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("ellipse", { cx: "20", cy: "12", rx: "14", ry: "6", fill: fill, stroke: stroke, strokeWidth: SW }), _jsx("text", { x: "20", y: "33", textAnchor: "middle", fill: "#7C3AED", fontSize: "14", fontWeight: "bold", fontFamily: "Arial, sans-serif", children: "G" })] }));
        default:
            return null;
    }
}
