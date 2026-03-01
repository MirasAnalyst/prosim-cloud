import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import TopNav from './TopNav';
import BottomPanel from './BottomPanel';
import EquipmentPalette from '../equipment/EquipmentPalette';
import FlowsheetCanvas from '../canvas/FlowsheetCanvas';
import PropertyInspector from '../inspector/PropertyInspector';
import AgentPanel from '../agent/AgentPanel';
import VersionPanel from '../version/VersionPanel';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useThemeStore } from '../../stores/themeStore';

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    const handler = (e: KeyboardEvent) => {
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
            saveFlowsheet(currentProjectId, nodes as any, edges as any)
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
      }

      // Undo/Redo/Copy/Paste — skip when focused on input elements
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

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
  const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <Toaster richColors position="bottom-right" theme={theme} />
      <TopNav onToggleSidebar={() => setSidebarOpen(prev => !prev)} />
      <div className="flex flex-1 overflow-hidden">
        <div className={`${sidebarOpen ? 'block' : 'hidden'} lg:block`}>
          <EquipmentPalette />
        </div>
        <FlowsheetCanvas />
        <div className="hidden lg:block">
          <PropertyInspector />
        </div>
        {/* Mobile property inspector overlay */}
        {selectedNodeId && (
          <div className="lg:hidden fixed inset-0 z-40">
            <div className="absolute inset-0 bg-black/40" onClick={() => setSelectedNode(null)} />
            <div className="absolute right-0 top-0 bottom-0 w-72 max-w-[85vw] z-50">
              <PropertyInspector />
            </div>
          </div>
        )}
      </div>
      <BottomPanel />
      <AgentPanel />
      <VersionPanel />
    </div>
  );
}
