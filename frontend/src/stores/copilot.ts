import { create } from 'zustand';

export interface CopilotMessage {
  id: string;
  sender: 'user' | 'copilot';
  text: string;
  timestamp: string;
}

interface CopilotState {
  isOpen: boolean;
  messages: CopilotMessage[];
  setIsOpen: (isOpen: boolean) => void;
  toggleOpen: () => void;
  addMessage: (message: Omit<CopilotMessage, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;
}

export const useCopilotStore = create<CopilotState>((set) => ({
  isOpen: false,
  messages: [
    {
      id: 'welcome',
      sender: 'copilot',
      text: 'Hello! I am your AegisX Security Intelligence Copilot. Ask me questions about asset exposures, threat campaign nodes, or posture risk recommendations. Please note that I am strictly an ADVISORY assistant.',
      timestamp: new Date().toISOString(),
    },
  ],
  setIsOpen: (isOpen) => set({ isOpen }),
  toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...msg,
          id: Math.random().toString(),
          timestamp: new Date().toISOString(),
        },
      ],
    })),
  clearMessages: () =>
    set({
      messages: [
        {
          id: 'welcome',
          sender: 'copilot',
          text: 'Context cleared. How can I assist you in your threat investigation?',
          timestamp: new Date().toISOString(),
        },
      ],
    }),
}));
