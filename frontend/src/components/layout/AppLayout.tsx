import TopNav from './TopNav';
import BottomPanel from './BottomPanel';
import EquipmentPalette from '../equipment/EquipmentPalette';
import FlowsheetCanvas from '../canvas/FlowsheetCanvas';
import PropertyInspector from '../inspector/PropertyInspector';
import AgentPanel from '../agent/AgentPanel';

export default function AppLayout() {
  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-gray-950 text-gray-100">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <EquipmentPalette />
        <FlowsheetCanvas />
        <PropertyInspector />
      </div>
      <BottomPanel />
      <AgentPanel />
    </div>
  );
}
