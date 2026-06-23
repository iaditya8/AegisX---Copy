import React from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = 'An unexpected system error occurred', onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-red-950/40 bg-red-950/10 max-w-lg mx-auto my-6 space-y-4">
      <div className="p-3 bg-red-950/20 rounded-xl border border-red-900/30 text-red-500 shadow-md">
        <AlertOctagon className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-red-400 tracking-tight">System Request Failed</h3>
        <p className="text-xs text-zinc-400 max-w-sm mx-auto leading-relaxed">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-lg shadow-sm transition-all duration-150 cursor-pointer"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Retry Connection
        </button>
      )}
    </div>
  );
}
