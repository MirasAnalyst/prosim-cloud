import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState, useRef } from 'react';
const PROMPT_TEXT = 'Design a natural gas processing plant with inlet separator, demethanizer, and NGL recovery...';
const TYPING_MS = 21;
const THINKING_MS = 400;
const NODE_START = 2.4;
const NODE_STAGGER = 0.25;
const PIPE_START = 3.8;
const PIPE_STAGGER = 0.25;
const LABEL_START = 5.2;
const LABEL_STAGGER = 0.15;
const FLOW_START_MS = 6200;
const FADEOUT_START_MS = 7800;
const CYCLE_MS = 8500;
const NODES = [
    { id: 'M-101', label: 'M-101', sublabel: 'Mixer', x: 95, y: 124, w: 56, h: 48, shape: 'mixer' },
    { id: 'E-101', label: 'E-101', sublabel: 'Heat Exchanger', x: 200, y: 118, w: 100, h: 58, detail: 'Q = -1,240 kW', shape: 'hx' },
    { id: 'V-101', label: 'V-101', sublabel: '2-Phase Sep.', x: 350, y: 124, w: 80, h: 48, detail: '28 bar', shape: 'separator' },
    { id: 'K-101', label: 'K-101', sublabel: 'Compressor', x: 448, y: 38, w: 102, h: 54, detail: 'W = 850 kW', shape: 'compressor' },
    { id: 'E-102', label: 'E-102', sublabel: 'Cooler', x: 478, y: 128, w: 72, h: 46, detail: '40\u00B0C out', shape: 'cooler' },
    { id: 'T-101', label: 'T-101', sublabel: 'Demethanizer', x: 258, y: 216, w: 44, h: 90, detail: '12 stages', shape: 'column' },
];
const PIPES = [
    'M 40 148 L 95 148',
    'M 151 148 L 200 148',
    'M 300 148 L 350 148',
    'M 430 132 L 430 65 L 448 65',
    'M 430 164 L 430 261 L 302 261',
    'M 550 65 L 570 65 L 570 151 L 550 151',
    'M 514 174 L 514 200',
];
const LABELS = [
    { id: 'S-1', x: 28, y: 118, w: 48, h: 22, text: 'S-1', sub: '25\u00B0C 30bar', type: 'stream' },
    { id: 'S-2', x: 153, y: 118, w: 44, h: 22, text: 'S-2', sub: '28\u00B0C 29bar', type: 'stream' },
    { id: 'S-3', x: 303, y: 118, w: 48, h: 22, text: 'S-3', sub: '-30\u00B0C 28bar', type: 'stream' },
    { id: 'S-4', x: 435, y: 82, w: 28, h: 20, text: 'S-4', sub: 'Vapor', type: 'stream' },
    { id: 'S-5', x: 435, y: 182, w: 28, h: 20, text: 'S-5', sub: 'Liquid', type: 'stream' },
    { id: 'SG', x: 488, y: 202, w: 52, h: 18, text: 'Sales Gas', type: 'product' },
    { id: 'NGL', x: 210, y: 216, w: 40, h: 18, text: 'NGL', type: 'product' },
];
function NodeGroup({ node, index }) {
    const cx = node.x + node.w / 2;
    const cy = node.y + node.h / 2;
    const inputColor = (node.shape === 'hx' || node.shape === 'cooler') ? '#F59E0B' : '#4CAF50';
    const outputColor = (node.shape === 'hx' || node.shape === 'cooler') ? '#F59E0B' : '#2196F3';
    const renderShape = () => {
        switch (node.shape) {
            case 'mixer':
                return _jsx("circle", { cx: cx, cy: cy, r: 14, fill: "#1a2332", stroke: "#4a6278", strokeWidth: "1.5" });
            case 'hx':
                return (_jsxs(_Fragment, { children: [_jsx("rect", { x: node.x, y: node.y, width: node.w, height: node.h, rx: 8, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" }), [0, 1, 2].map(i => {
                            const ly = node.y + node.h * 0.25 + i * (node.h * 0.25);
                            return _jsx("line", { x1: node.x + 12, x2: node.x + node.w - 12, y1: ly, y2: ly, stroke: "#4a6278", opacity: 0.3 }, i);
                        })] }));
            case 'separator':
                return _jsx("rect", { x: node.x, y: node.y, width: node.w, height: node.h, rx: node.h / 2, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" });
            case 'compressor': {
                const cr = 15;
                const ccx = node.x + cr + 5;
                const triL = node.x + cr * 2 + 8;
                const triR = node.x + node.w - 10;
                return (_jsxs(_Fragment, { children: [_jsx("circle", { cx: ccx, cy: cy, r: cr, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" }), _jsx("path", { d: `M${triL} ${cy - 14} L${triR} ${cy} L${triL} ${cy + 14} Z`, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" })] }));
            }
            case 'cooler':
                return _jsx("rect", { x: node.x, y: node.y, width: node.w, height: node.h, rx: 6, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" });
            case 'column':
                return (_jsxs(_Fragment, { children: [_jsx("rect", { x: node.x, y: node.y, width: node.w, height: node.h, rx: node.w / 2, fill: "url(#metalGrad)", stroke: "#4a6278", strokeWidth: "1.5" }), [1, 2, 3, 4, 5].map(i => {
                            const ly = node.y + (i / 6) * node.h;
                            return _jsx("line", { x1: node.x + 4, x2: node.x + node.w - 4, y1: ly, y2: ly, stroke: "#4a6278", strokeDasharray: "4 3", opacity: 0.25 }, i);
                        })] }));
        }
    };
    return (_jsxs("g", { className: `node node-${index}`, style: { animationDelay: `${NODE_START + index * NODE_STAGGER}s` }, children: [renderShape(), _jsx("rect", { x: cx - 20, y: cy - 7, width: 40, height: 14, rx: 3, fill: "#1e293b", stroke: "#334155", strokeWidth: "0.5" }), _jsx("text", { x: cx, y: cy + 2.5, fill: "#e2e8f0", fontSize: "7", textAnchor: "middle", fontFamily: "sans-serif", fontWeight: "600", children: node.label }), node.sublabel && (_jsx("text", { x: cx, y: node.y + node.h + 11, fill: "#64748b", fontSize: "6.5", textAnchor: "middle", fontFamily: "sans-serif", children: node.sublabel })), node.detail && (_jsx("text", { x: cx, y: node.y + node.h + 21, fill: "#3b82f6", fontSize: "6.5", textAnchor: "middle", fontFamily: "monospace", children: node.detail })), _jsx("circle", { cx: node.x, cy: cy, r: 2.5, fill: inputColor, stroke: "#1e293b", strokeWidth: "1" }), node.shape === 'separator' ? (_jsxs(_Fragment, { children: [_jsx("circle", { cx: node.x + node.w, cy: node.y + 8, r: 2.5, fill: outputColor, stroke: "#1e293b", strokeWidth: "1" }), _jsx("circle", { cx: node.x + node.w, cy: node.y + node.h - 8, r: 2.5, fill: outputColor, stroke: "#1e293b", strokeWidth: "1" })] })) : (_jsx("circle", { cx: node.x + node.w, cy: cy, r: 2.5, fill: outputColor, stroke: "#1e293b", strokeWidth: "1" })), node.shape === 'cooler' && (_jsx("circle", { cx: cx, cy: node.y + node.h, r: 2.5, fill: outputColor, stroke: "#1e293b", strokeWidth: "1" }))] }));
}
function PipeGroup({ d, index, flowing }) {
    const delay = `${PIPE_START + index * PIPE_STAGGER}s`;
    return (_jsxs("g", { className: `pipe pipe-${index}`, children: [_jsx("path", { d: d, fill: "none", stroke: "#000", strokeWidth: "4", strokeLinecap: "round", strokeLinejoin: "round", pathLength: 1, className: "pipe-draw", style: { animationDelay: delay } }), _jsx("path", { d: d, fill: "none", stroke: "#888", strokeWidth: "2.5", strokeLinecap: "round", strokeLinejoin: "round", pathLength: 1, className: "pipe-draw", style: { animationDelay: delay } }), _jsx("path", { d: d, fill: "none", stroke: "white", strokeWidth: "1.5", strokeLinecap: "round", strokeLinejoin: "round", pathLength: 1, className: `pipe-draw ${flowing ? 'pipe-flowing' : ''}`, style: { animationDelay: delay } })] }));
}
function StreamLabel({ label, index }) {
    const cx = label.x + label.w / 2;
    const isProduct = label.type === 'product';
    return (_jsxs("g", { className: `label label-${index}`, style: { animationDelay: `${LABEL_START + index * LABEL_STAGGER}s` }, children: [_jsx("rect", { x: label.x, y: label.y, width: label.w, height: label.h, rx: 4, fill: isProduct ? '#064e3b' : '#1e293b', stroke: isProduct ? '#065f46' : '#334155', strokeWidth: "0.5" }), _jsx("text", { x: cx, y: label.y + (label.sub ? label.h * 0.45 : label.h * 0.65), fill: isProduct ? '#6ee7b7' : '#60a5fa', fontSize: isProduct ? '6.5' : '7', textAnchor: "middle", fontFamily: "monospace", fontWeight: "bold", children: label.text }), label.sub && (_jsx("text", { x: cx, y: label.y + label.h * 0.85, fill: "#64748b", fontSize: "6", textAnchor: "middle", fontFamily: "monospace", children: label.sub }))] }));
}
const ANIMATION_CSS = `
  .node { opacity: 0; transform-origin: center; transform-box: fill-box; animation: nodeAppear 0.5s ease-out forwards; }
  @keyframes nodeAppear { 0% { opacity: 0; transform: scale(0.85); } 100% { opacity: 1; transform: scale(1); } }
  .pipe-draw { stroke-dasharray: 1; stroke-dashoffset: 1; animation: pipeDraw 0.6s ease-in-out forwards; }
  @keyframes pipeDraw { 0% { stroke-dashoffset: 1; } 100% { stroke-dashoffset: 0; } }
  .pipe-flowing { stroke-dasharray: 4 3 !important; stroke-dashoffset: 0 !important; animation: dash 0.8s linear infinite !important; }
  @keyframes dash { to { stroke-dashoffset: -20; } }
  .label { opacity: 0; animation: labelFade 0.4s ease-out forwards; }
  @keyframes labelFade { 0% { opacity: 0; transform: translateY(3px); } 100% { opacity: 1; transform: translateY(0); } }
  @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
  .cursor-blink { animation: blink 0.8s step-end infinite; }
  @keyframes thinking { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
  .thinking-dots span { animation: thinking 1.2s ease-in-out infinite; }
  .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
  .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
`;
export default function FlowsheetMockup() {
    const [cycle, setCycle] = useState(0);
    const [charIndex, setCharIndex] = useState(0);
    const [pipesFlowing, setPipesFlowing] = useState(false);
    const [fading, setFading] = useState(false);
    const [showThinking, setShowThinking] = useState(false);
    const timersRef = useRef([]);
    useEffect(() => {
        timersRef.current.forEach(clearTimeout);
        timersRef.current = [];
        setCharIndex(0);
        setPipesFlowing(false);
        setFading(false);
        setShowThinking(false);
        let idx = 0;
        const typingInterval = setInterval(() => {
            idx++;
            setCharIndex(idx);
            if (idx >= PROMPT_TEXT.length)
                clearInterval(typingInterval);
        }, TYPING_MS);
        timersRef.current.push(typingInterval);
        const thinkTimer = setTimeout(() => setShowThinking(true), PROMPT_TEXT.length * TYPING_MS);
        timersRef.current.push(thinkTimer);
        const hideThinkTimer = setTimeout(() => setShowThinking(false), PROMPT_TEXT.length * TYPING_MS + THINKING_MS);
        timersRef.current.push(hideThinkTimer);
        const flowTimer = setTimeout(() => setPipesFlowing(true), FLOW_START_MS);
        timersRef.current.push(flowTimer);
        const fadeTimer = setTimeout(() => setFading(true), FADEOUT_START_MS);
        timersRef.current.push(fadeTimer);
        const restartTimer = setTimeout(() => setCycle((c) => c + 1), CYCLE_MS);
        timersRef.current.push(restartTimer);
        return () => {
            clearInterval(typingInterval);
            timersRef.current.forEach(clearTimeout);
            timersRef.current = [];
        };
    }, [cycle]);
    return (_jsxs("div", { className: "relative", children: [_jsx("div", { className: "absolute inset-0 bg-blue-500/10 rounded-3xl blur-2xl" }), _jsx("div", { className: "relative", children: _jsxs("div", { className: "bg-gray-900 dark:bg-gray-800 rounded-xl overflow-hidden border border-gray-700 shadow-2xl", children: [_jsxs("div", { className: "flex items-center px-4 py-3 bg-gray-800 border-b border-gray-700", children: [_jsxs("div", { className: "flex space-x-2 mr-4", children: [_jsx("div", { className: "w-3 h-3 rounded-full bg-red-500" }), _jsx("div", { className: "w-3 h-3 rounded-full bg-yellow-500" }), _jsx("div", { className: "w-3 h-3 rounded-full bg-green-500" })] }), _jsx("span", { className: "text-xs text-gray-400 font-medium", children: "ProSim Cloud \u2014 Flowsheet Builder" })] }), _jsxs("div", { className: "relative bg-[#0a0f1a]", style: { opacity: fading ? 0 : 1, transition: 'opacity 0.5s ease-out' }, children: [_jsx("style", { children: ANIMATION_CSS }), _jsxs("svg", { viewBox: "0 0 620 320", className: "w-full h-auto", xmlns: "http://www.w3.org/2000/svg", children: [_jsxs("defs", { children: [_jsx("pattern", { id: "dotgrid", width: "20", height: "20", patternUnits: "userSpaceOnUse", children: _jsx("circle", { cx: "10", cy: "10", r: "0.8", fill: "#1e293b" }) }), _jsxs("linearGradient", { id: "metalGrad", x1: "0%", y1: "0%", x2: "100%", y2: "0%", children: [_jsx("stop", { offset: "0%", stopColor: "#2a3545" }), _jsx("stop", { offset: "25%", stopColor: "#3d4f63" }), _jsx("stop", { offset: "50%", stopColor: "#4a5f78" }), _jsx("stop", { offset: "75%", stopColor: "#3d4f63" }), _jsx("stop", { offset: "100%", stopColor: "#2a3545" })] })] }), _jsx("rect", { width: "620", height: "320", fill: "#0a0f1a" }), _jsx("rect", { width: "620", height: "320", fill: "url(#dotgrid)" }), PIPES.map((d, i) => _jsx(PipeGroup, { d: d, index: i, flowing: pipesFlowing }, i)), NODES.map((node, i) => _jsx(NodeGroup, { node: node, index: i }, node.id)), LABELS.map((label, i) => _jsx(StreamLabel, { label: label, index: i }, label.id))] }, cycle)] }), _jsx("div", { className: "px-4 py-3 bg-gray-900 border-t border-gray-700", children: _jsxs("div", { className: "flex items-center bg-gray-800 rounded-lg border border-gray-700 px-4 py-2.5", children: [_jsx("svg", { className: "w-4 h-4 text-blue-500 mr-3 flex-shrink-0", fill: "none", viewBox: "0 0 24 24", stroke: "currentColor", strokeWidth: 2, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" }) }), _jsx("span", { className: "text-sm text-gray-400 truncate", children: PROMPT_TEXT.slice(0, charIndex) }), showThinking ? (_jsxs("span", { className: "thinking-dots text-blue-400 text-sm ml-1 flex-shrink-0", children: [_jsx("span", { children: "." }), _jsx("span", { children: "." }), _jsx("span", { children: "." })] })) : (_jsx("span", { className: "w-0.5 h-4 bg-blue-500 ml-0.5 flex-shrink-0 cursor-blink" }))] }) })] }) })] }));
}
