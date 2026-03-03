import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import TopNav from './TopNav';
import BottomPanel from './BottomPanel';
import EquipmentPalette from '../equipment/EquipmentPalette';
import FlowsheetCanvas from '../canvas/FlowsheetCanvas';
import PropertyInspector from '../inspector/PropertyInspector';
import StreamInspector from '../inspector/StreamInspector';
import AgentPanel from '../agent/AgentPanel';
import VersionPanel from '../version/VersionPanel';
import SimulationBasisPanel from '../basis/SimulationBasisPanel';
import SensitivityPanel from '../analysis/SensitivityPanel';
import CaseManagerPanel from '../analysis/CaseManagerPanel';
import OptimizationPanel from '../analysis/OptimizationPanel';
import DynamicPanel from '../analysis/DynamicPanel';
import PinchPanel from '../tools/PinchPanel';
import UtilityPanel from '../tools/UtilityPanel';
import EmissionsPanel from '../tools/EmissionsPanel';
import ReliefValvePanel from '../tools/ReliefValvePanel';
import HydraulicsPanel from '../tools/HydraulicsPanel';
import ControlValvePanel from '../tools/ControlValvePanel';
import PhaseEnvelopePanel from '../tools/PhaseEnvelopePanel';
import BinaryVLEPanel from '../tools/BinaryVLEPanel';
import ColumnProfilePanel from '../analysis/ColumnProfilePanel';
import InsightsPanel from '../analysis/InsightsPanel';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useThemeStore } from '../../stores/themeStore';
export default function AppLayout() {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [basisOpen, setBasisOpen] = useState(false);
    const [sensitivityOpen, setSensitivityOpen] = useState(false);
    const [casesOpen, setCasesOpen] = useState(false);
    const [optimizationOpen, setOptimizationOpen] = useState(false);
    const [dynamicOpen, setDynamicOpen] = useState(false);
    const [pinchOpen, setPinchOpen] = useState(false);
    const [utilityOpen, setUtilityOpen] = useState(false);
    const [emissionsOpen, setEmissionsOpen] = useState(false);
    const [reliefValveOpen, setReliefValveOpen] = useState(false);
    const [hydraulicsOpen, setHydraulicsOpen] = useState(false);
    const [controlValveOpen, setControlValveOpen] = useState(false);
    const [phaseEnvelopeOpen, setPhaseEnvelopeOpen] = useState(false);
    const [binaryVLEOpen, setBinaryVLEOpen] = useState(false);
    const [columnProfileOpen, setColumnProfileOpen] = useState(false);
    const [insightsOpen, setInsightsOpen] = useState(false);
    const initProject = useFlowsheetStore((s) => s.initProject);
    const theme = useThemeStore((s) => s.theme);
    useEffect(() => {
        document.documentElement.classList.toggle('dark', theme === 'dark');
    }, [theme]);
    useEffect(() => {
        initProject().then(() => {
            const projectId = useFlowsheetStore.getState().currentProjectId;
            if (projectId) {
                useAgentStore.getState().loadChatHistory(projectId);
            }
        });
    }, [initProject]);
    // Keyboard shortcuts
    useEffect(() => {
        const handler = (e) => {
            const mod = e.metaKey || e.ctrlKey;
            if (mod && e.key === 's') {
                e.preventDefault();
                const state = useFlowsheetStore.getState();
                // Trigger a save by calling the internal debounce mechanism
                // We access the store's save logic through loadFlowsheet-like trigger
                const { currentProjectId, nodes, edges } = state;
                if (currentProjectId) {
                    import('../../lib/api-client').then(({ saveFlowsheet }) => {
                        useFlowsheetStore.setState({ saveStatus: 'saving' });
                        saveFlowsheet(currentProjectId, nodes, edges)
                            .then(() => useFlowsheetStore.setState({ saveStatus: 'saved' }))
                            .catch(() => useFlowsheetStore.setState({ saveStatus: 'error' }));
                    });
                }
            }
            if (mod && e.key === 'Enter') {
                e.preventDefault();
                useSimulationStore.getState().runSimulation();
            }
            if (e.key === 'Escape') {
                useFlowsheetStore.getState().setSelectedNode(null);
                useFlowsheetStore.getState().setSelectedEdge(null);
            }
            // Undo/Redo/Copy/Paste — skip when focused on input elements
            const tag = e.target?.tagName?.toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select')
                return;
            if (mod && e.shiftKey && e.key === 'Z') {
                e.preventDefault();
                useFlowsheetStore.getState().redo();
                return;
            }
            if (mod && e.key === 'z') {
                e.preventDefault();
                useFlowsheetStore.getState().undo();
                return;
            }
            if (mod && e.key === 'c') {
                e.preventDefault();
                useFlowsheetStore.getState().copySelected();
            }
            if (mod && e.key === 'v') {
                e.preventDefault();
                useFlowsheetStore.getState().pasteClipboard();
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);
    const selectedNodeId = useFlowsheetStore((s) => s.selectedNodeId);
    const selectedEdgeId = useFlowsheetStore((s) => s.selectedEdgeId);
    const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);
    const setSelectedEdge = useFlowsheetStore((s) => s.setSelectedEdge);
    return (_jsxs("div", { className: "h-screen w-screen flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100", children: [_jsx(Toaster, { richColors: true, position: "bottom-right", theme: theme }), _jsx(TopNav, { onToggleSidebar: () => setSidebarOpen(prev => !prev), onToggleBasis: () => setBasisOpen(prev => !prev), basisOpen: basisOpen, onToggleSensitivity: () => setSensitivityOpen(prev => !prev), onToggleCases: () => setCasesOpen(prev => !prev), onToggleDesignSpec: () => { }, onToggleOptimization: () => setOptimizationOpen(prev => !prev), onToggleDynamic: () => setDynamicOpen(prev => !prev), onTogglePinch: () => setPinchOpen(prev => !prev), onToggleUtility: () => setUtilityOpen(prev => !prev), onToggleEmissions: () => setEmissionsOpen(prev => !prev), onToggleReliefValve: () => setReliefValveOpen(prev => !prev), onToggleHydraulics: () => setHydraulicsOpen(prev => !prev), onToggleControlValve: () => setControlValveOpen(prev => !prev), onTogglePhaseEnvelope: () => setPhaseEnvelopeOpen(prev => !prev), onToggleBinaryVLE: () => setBinaryVLEOpen(prev => !prev), onToggleColumnProfile: () => setColumnProfileOpen(prev => !prev), onToggleInsights: () => setInsightsOpen(prev => !prev) }), _jsxs("div", { className: "flex flex-1 overflow-hidden", children: [_jsx("div", { className: `${sidebarOpen ? 'block' : 'hidden'} lg:block`, children: _jsx(EquipmentPalette, {}) }), _jsx(FlowsheetCanvas, {}), _jsx("div", { className: "hidden lg:block", children: selectedEdgeId ? _jsx(StreamInspector, {}) : _jsx(PropertyInspector, {}) }), (selectedNodeId || selectedEdgeId) && (_jsxs("div", { className: "lg:hidden fixed inset-0 z-40", children: [_jsx("div", { className: "absolute inset-0 bg-black/40", onClick: () => { setSelectedNode(null); setSelectedEdge(null); } }), _jsx("div", { className: "absolute right-0 top-0 bottom-0 w-72 max-w-[85vw] z-50", children: selectedEdgeId ? _jsx(StreamInspector, {}) : _jsx(PropertyInspector, {}) })] }))] }), _jsx(BottomPanel, {}), _jsx(AgentPanel, {}), _jsx(VersionPanel, {}), _jsx(SimulationBasisPanel, { open: basisOpen, onClose: () => setBasisOpen(false) }), _jsx(SensitivityPanel, { open: sensitivityOpen, onClose: () => setSensitivityOpen(false) }), _jsx(CaseManagerPanel, { open: casesOpen, onClose: () => setCasesOpen(false) }), _jsx(OptimizationPanel, { open: optimizationOpen, onClose: () => setOptimizationOpen(false) }), _jsx(DynamicPanel, { open: dynamicOpen, onClose: () => setDynamicOpen(false) }), _jsx(PinchPanel, { open: pinchOpen, onClose: () => setPinchOpen(false) }), _jsx(UtilityPanel, { open: utilityOpen, onClose: () => setUtilityOpen(false) }), _jsx(EmissionsPanel, { open: emissionsOpen, onClose: () => setEmissionsOpen(false) }), _jsx(ReliefValvePanel, { open: reliefValveOpen, onClose: () => setReliefValveOpen(false) }), _jsx(HydraulicsPanel, { open: hydraulicsOpen, onClose: () => setHydraulicsOpen(false) }), _jsx(ControlValvePanel, { open: controlValveOpen, onClose: () => setControlValveOpen(false) }), _jsx(PhaseEnvelopePanel, { open: phaseEnvelopeOpen, onClose: () => setPhaseEnvelopeOpen(false) }), _jsx(BinaryVLEPanel, { open: binaryVLEOpen, onClose: () => setBinaryVLEOpen(false) }), _jsx(ColumnProfilePanel, { open: columnProfileOpen, onClose: () => setColumnProfileOpen(false) }), _jsx(InsightsPanel, { open: insightsOpen, onClose: () => setInsightsOpen(false) })] }));
}
