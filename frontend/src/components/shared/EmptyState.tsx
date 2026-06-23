import React from 'react';
import { AlertCircle } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export function EmptyState({
  title,
  description,
  icon = <AlertCircle className="h-8 w-8 text-zinc-600" />,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/20 max-w-md mx-auto my-6 space-y-4">
      <div className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800/80 shadow-md">
        {icon}
      </div>
      <div className="space-y-1.5">
        <h3 className="text-sm font-semibold text-zinc-200 tracking-tight">{title}</h3>
        <p className="text-xs text-zinc-500 max-w-xs mx-auto leading-relaxed">{description}</p>
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
