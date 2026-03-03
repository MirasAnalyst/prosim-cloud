import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Bot, User, Info, CheckCircle2 } from 'lucide-react';
export default function ChatMessage({ message }) {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';
    return (_jsxs("div", { className: `flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`, children: [_jsx("div", { className: `flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${isUser
                    ? 'bg-blue-500/20 text-blue-400'
                    : isSystem
                        ? 'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                        : 'bg-purple-500/20 text-purple-400'}`, children: isUser ? _jsx(User, { size: 14 }) : isSystem ? _jsx(Info, { size: 14 }) : _jsx(Bot, { size: 14 }) }), _jsxs("div", { className: `flex-1 rounded-lg px-3 py-2 text-sm ${isUser
                    ? 'bg-blue-500/20 text-blue-900 dark:text-blue-100 rounded-tr-none'
                    : isSystem
                        ? 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 italic'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-none'}`, children: [_jsx("p", { className: "whitespace-pre-wrap leading-relaxed", children: message.content }), message.flowsheetAction && (_jsxs("div", { className: "flex items-center gap-1.5 mt-2 px-2 py-1 rounded bg-green-500/15 text-green-400 text-xs w-fit", children: [_jsx(CheckCircle2, { size: 12 }), _jsxs("span", { children: ["Created ", message.flowsheetAction.equipmentCount, " equipment items with", ' ', message.flowsheetAction.connectionCount, " connections"] })] })), _jsx("span", { className: "block text-[10px] text-gray-500 mt-1", children: message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                        }) })] })] }));
}
