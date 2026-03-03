import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    const bottomRef = useRef(null);
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);
    if (!isOpen)
        return null;
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-2xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: "w-2 h-2 rounded-full bg-green-400 animate-pulse" }), _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "AI Assistant" })] }), _jsxs("div", { className: "flex items-center gap-1", children: [_jsx("button", { onClick: clearMessages, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200", title: "Clear chat", children: _jsx(Trash2, { size: 14 }) }), _jsx("button", { onClick: togglePanel, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200", children: _jsx(X, { size: 16 }) })] })] }), _jsxs("div", { className: "flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4", children: [messages.map((msg) => (_jsx(ChatMessage, { message: msg }, msg.id))), isLoading && (_jsxs("div", { className: "flex items-center gap-2 text-gray-500 dark:text-gray-400 text-sm", children: [_jsx(Loader2, { size: 14, className: "animate-spin" }), _jsx("span", { children: "Thinking..." })] })), messages.length <= 1 && (_jsxs("div", { className: "space-y-2 mt-4", children: [_jsx("p", { className: "text-xs text-gray-500 uppercase tracking-wider mb-2", children: "Suggestions" }), suggestions.map((s) => (_jsx(SuggestionCard, { text: s, onClick: () => sendMessage(s) }, s)))] })), _jsx("div", { ref: bottomRef })] }), _jsx(AgentInput, { onSend: sendMessage, disabled: isLoading })] }));
}
