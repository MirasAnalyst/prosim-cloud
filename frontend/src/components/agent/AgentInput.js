import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { SendHorizontal } from 'lucide-react';
export default function AgentInput({ onSend, disabled }) {
    const [value, setValue] = useState('');
    const handleSend = () => {
        const trimmed = value.trim();
        if (!trimmed || disabled)
            return;
        onSend(trimmed);
        setValue('');
    };
    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };
    return (_jsxs("div", { className: "flex items-center gap-2 p-3 border-t border-gray-200 dark:border-gray-800", children: [_jsx("input", { type: "text", value: value, onChange: (e) => setValue(e.target.value), onKeyDown: handleKeyDown, placeholder: "Ask the AI assistant...", disabled: disabled, className: "flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50" }), _jsx("button", { onClick: handleSend, disabled: disabled || !value.trim(), className: "p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-30 disabled:hover:bg-blue-600 transition-colors", children: _jsx(SendHorizontal, { size: 16 }) })] }));
}
