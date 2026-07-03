'use client';

import React, { useState } from 'react';
import { useCopilotStore } from '../../stores/copilot';
import { useScopeStore } from '../../stores/scope';
import { useAskCopilot, useCopilotHistoryList } from '../../hooks/useCopilot';
import { 
  Sparkles, 
  X, 
  Send, 
  AlertTriangle, 
  Clock, 
  CheckCircle,
  HelpCircle,
  Trash2,
  ExternalLink
} from 'lucide-react';

export function CopilotDrawer() {
  const { isOpen, setIsOpen, messages, addMessage, clearMessages } = useCopilotStore();
  const { selectedScopeId } = useScopeStore();
  const scopeId = selectedScopeId || undefined;

  const askCopilotMutation = useAskCopilot();
  const { data: history = [], refetch: refetchHistory } = useCopilotHistoryList();

  const [prompt, setPrompt] = useState('');
  const [activeReference, setActiveReference] = useState<any | null>(null);

  if (!isOpen) return null;

  const handleSendPrompt = async (textToSend: string) => {
    if (!textToSend.trim()) return;

    // Append user message
    addMessage({
      sender: 'user',
      text: textToSend,
    });

    try {
      const response = await askCopilotMutation.mutateAsync({
        prompt: textToSend,
        scopeId,
      });

      // Append Copilot response
      addMessage({
        sender: 'copilot',
        text: response.answer,
      });

      // Refresh audit logs
      refetchHistory();
    } catch (err) {
      console.error(err);
      addMessage({
        sender: 'copilot',
        text: 'Sorry, I encountered an error communicating with the advisory engine.',
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const txt = prompt;
    setPrompt('');
    handleSendPrompt(txt);
  };

  // Helper to parse citations and make them clickable
  const renderMessageText = (text: string) => {
    // Regex looking for markdown links like [Label](type:id)
    const regex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      // Add text before match
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      const label = match[1];
      const linkInfo = match[2]; // e.g. "asset:123" or "finding:456"
      const [type, id] = linkInfo.split(':');

      parts.push(
        <button
          key={match.index}
          onClick={() => setActiveReference({ label, type, id })}
          className="text-indigo-400 hover:text-indigo-300 font-bold underline bg-indigo-950/20 px-1 rounded inline-flex items-center gap-0.5 mx-0.5 text-[10px] cursor-pointer"
        >
          {label}
          <ExternalLink className="w-2.5 h-2.5 inline" />
        </button>
      );

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  const pastQueries = [
    'What are the critical posture drift items?',
    'How do I mitigate MFA disabled on root account?',
    'Show GRC assessment status',
  ];

  return (
    <div className="fixed top-0 right-0 h-screen w-96 bg-zinc-950 border-l border-zinc-900 shadow-2xl z-50 flex flex-col overflow-hidden animate-slide-in">
      {/* Header */}
      <div className="p-4 border-b border-zinc-900 bg-zinc-950/90 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-500 animate-pulse" />
          <h2 className="text-sm font-bold text-white tracking-wide">AegisX AI Copilot</h2>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={clearMessages}
            title="Clear Chat context"
            className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-zinc-900 rounded transition-all cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-900 rounded transition-all cursor-pointer"
          >
            <X className="w-4.5 h-4.5" />
          </button>
        </div>
      </div>

      {/* Advisory Banner */}
      <div className="bg-amber-950/15 border-b border-amber-900/30 p-3 shrink-0 flex items-start gap-2.5">
        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="text-[9px] font-bold text-amber-500 uppercase tracking-wide block">Advisory Only</span>
          <p className="text-[9px] text-zinc-400 leading-normal">
            The Copilot cannot execute commands or modify platform configurations. Read-only advisory access.
          </p>
        </div>
      </div>

      {/* Chat Messages Log */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, idx) => (
          <div
            key={m.id || idx}
            className={`flex flex-col max-w-[85%] space-y-1 ${
              m.sender === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'
            }`}
          >
            <div className="flex items-center gap-1 text-[8px] text-zinc-500 font-mono">
              <span>{m.sender === 'user' ? 'Analyst' : 'Copilot'}</span>
            </div>
            <div
              className={`p-3 rounded-2xl text-[11px] leading-relaxed font-mono ${
                m.sender === 'user'
                  ? 'bg-indigo-650 text-white rounded-br-none'
                  : 'bg-zinc-900 text-zinc-300 rounded-bl-none border border-zinc-800/80'
              }`}
            >
              {renderMessageText(m.text)}
            </div>
          </div>
        ))}

        {askCopilotMutation.isPending && (
          <div className="flex flex-col items-start max-w-[85%] space-y-1 mr-auto animate-pulse">
            <div className="text-[8px] text-zinc-500 font-mono">Copilot</div>
            <div className="p-3 rounded-2xl text-[11px] bg-zinc-900 border border-zinc-800/80 text-zinc-500 rounded-bl-none">
              Analyzing exposures...
            </div>
          </div>
        )}
      </div>

      {/* Reference Inspector overlay if item is clicked */}
      {activeReference && (
        <div className="absolute inset-x-0 bottom-16 bg-zinc-900 border-t border-zinc-800 p-4 space-y-2 animate-slide-up z-20">
          <div className="flex justify-between items-center">
            <span className="text-[9px] font-bold text-indigo-400 font-mono uppercase tracking-wider">
              Citation Inspector: {activeReference.type}
            </span>
            <button
              onClick={() => setActiveReference(null)}
              className="text-zinc-500 hover:text-zinc-200 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <h3 className="text-xs font-bold text-white">{activeReference.label}</h3>
          <p className="text-[9px] text-zinc-400 font-mono leading-normal">
            Entity ID Reference Key: {activeReference.id}
          </p>
        </div>
      )}

      {/* Quick query tags (only if prompt is empty) */}
      {!prompt && (
        <div className="p-3 border-t border-zinc-900 bg-zinc-950 shrink-0 space-y-1.5">
          <span className="text-[8px] text-zinc-500 uppercase tracking-widest block font-bold">Suggested Prompts:</span>
          <div className="flex flex-col gap-1.5">
            {pastQueries.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSendPrompt(q)}
                className="w-full text-left bg-zinc-900/50 hover:bg-zinc-900 border border-zinc-850 hover:border-zinc-800 text-[10px] text-zinc-400 py-1.5 px-2.5 rounded transition-all cursor-pointer truncate"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input footer */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-zinc-900 bg-zinc-950 shrink-0 flex gap-2">
        <input
          type="text"
          placeholder="Ask advisory question..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="flex-1 bg-zinc-900 border border-zinc-850 rounded-lg text-xs px-3 py-2 outline-none focus:border-indigo-500 text-zinc-300"
          required
        />
        <button
          type="submit"
          aria-label="Send Message"
          disabled={askCopilotMutation.isPending || !prompt.trim()}
          className="bg-indigo-650 hover:bg-indigo-600 disabled:bg-zinc-900 disabled:text-zinc-700 text-white p-2 rounded-lg cursor-pointer transition-all shrink-0 flex items-center justify-center"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
