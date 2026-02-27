import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import { type AgentMessage } from '../types';
import { agentChat } from '../lib/api-client';

interface AgentState {
  messages: AgentMessage[];
  isOpen: boolean;
  isLoading: boolean;

  sendMessage: (content: string) => Promise<void>;
  togglePanel: () => void;
  addMessage: (role: AgentMessage['role'], content: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  messages: [
    {
      id: uuidv4(),
      role: 'system',
      content: 'Welcome to ProSim Cloud AI Assistant. I can help you build and optimize your process flowsheet. Try asking me to add equipment or configure your simulation.',
      timestamp: new Date(),
    },
  ],
  isOpen: false,
  isLoading: false,

  sendMessage: async (content) => {
    const userMessage: AgentMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true,
    }));

    try {
      const chatMessages = get().messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const data = await agentChat(chatMessages);
      const assistantMessage: AgentMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: data.message?.content ?? 'No response received.',
        timestamp: new Date(),
      };
      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
      }));
    } catch {
      const errorMessage: AgentMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: 'Sorry, I was unable to connect to the AI service. Please check that the backend is running.',
        timestamp: new Date(),
      };
      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
      }));
    }
  },

  togglePanel: () => {
    set((state) => ({ isOpen: !state.isOpen }));
  },

  addMessage: (role, content) => {
    const message: AgentMessage = {
      id: uuidv4(),
      role,
      content,
      timestamp: new Date(),
    };
    set((state) => ({ messages: [...state.messages, message] }));
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },
}));
