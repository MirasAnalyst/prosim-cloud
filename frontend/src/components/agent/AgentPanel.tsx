import { useRef, useEffect } from 'react';
import { X, Loader2, Trash2 } from 'lucide-react';
import { useAgentStore } from '../../stores/agentStore';
import ChatMessage from './ChatMessage';
import AgentInput from './AgentInput';
import SuggestionCard from './SuggestionCard';

const suggestions = [
  'Build a natural gas plant with a heater to 150C, a separator, and compress the vapor to 5000 kPa',
  'What equipment do I need for distillation?',
  'Optimize the heat exchanger network',
  'Check my flowsheet for errors',
];

export default function AgentPanel() {
  const messages = useAgentStore((s) => s.messages);
  const isOpen = useAgentStore((s) => s.isOpen);
  const isLoading = useAgentStore((s) => s.isLoading);
  const togglePanel = useAgentStore((s) => s.togglePanel);
  const sendMessage = useAgentStore((s) => s.sendMessage);
  const clearMessages = useAgentStore((s) => s.clearMessages);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-12 bottom-0 w-96 bg-gray-900 border-l border-gray-800 z-40 flex flex-col shadow-2xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <h2 className="text-sm font-semibold text-gray-200">AI Assistant</h2>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearMessages}
            className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200"
            title="Clear chat"
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={togglePanel}
            className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Loader2 size={14} className="animate-spin" />
            <span>Thinking...</span>
          </div>
        )}

        {messages.length <= 1 && (
          <div className="space-y-2 mt-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
              Suggestions
            </p>
            {suggestions.map((s) => (
              <SuggestionCard
                key={s}
                text={s}
                onClick={() => sendMessage(s)}
              />
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <AgentInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
