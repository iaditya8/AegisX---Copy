import React from 'react';

interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingState({ message = 'Loading...', size = 'md' }: LoadingStateProps) {
  const spinnerSizes = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-2',
    lg: 'h-12 w-12 border-3',
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-4 animate-fade-in">
      <div
        className={`animate-spin rounded-full border-t-indigo-500 border-r-transparent border-b-indigo-500/20 border-l-transparent ${spinnerSizes[size]}`}
      />
      {message && (
        <p className="text-zinc-500 text-xs font-mono tracking-wider uppercase animate-pulse">
          {message}
        </p>
      )}
    </div>
  );
}
