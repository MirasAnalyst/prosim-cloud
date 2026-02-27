import { type AgentMessage } from '../../types';
import { Bot, User, Info } from 'lucide-react';

interface Props {
  message: AgentMessage;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-blue-500/20 text-blue-400'
            : isSystem
            ? 'bg-gray-700 text-gray-400'
            : 'bg-purple-500/20 text-purple-400'
        }`}
      >
        {isUser ? <User size={14} /> : isSystem ? <Info size={14} /> : <Bot size={14} />}
      </div>
      <div
        className={`flex-1 rounded-lg px-3 py-2 text-sm ${
          isUser
            ? 'bg-blue-500/20 text-blue-100 rounded-tr-none'
            : isSystem
            ? 'bg-gray-800 text-gray-400 italic'
            : 'bg-gray-800 text-gray-200 rounded-tl-none'
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        <span className="block text-[10px] text-gray-500 mt-1">
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </div>
  );
}
