import React from 'react';

type BadgeVariant = 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success' | 'warning' | 'error' | 'default';

interface StatusBadgeProps {
  value: string;
  variant?: BadgeVariant;
}

export function StatusBadge({ value, variant }: StatusBadgeProps) {
  const normValue = value.toLowerCase().trim();

  // Deduce variant if not explicitly provided
  const getVariant = (): BadgeVariant => {
    if (variant) return variant;

    if (['critical'].includes(normValue)) return 'critical';
    if (['high', 'failed', 'cancelled', 'disabled'].includes(normValue)) return 'high';
    if (['medium', 'running', 'pending', 'warning'].includes(normValue)) return 'medium';
    if (['low', 'info', 'draft', 'default'].includes(normValue)) return 'info';
    if (['completed', 'active', 'resolved', 'success', 'acknowledged'].includes(normValue)) return 'success';

    return 'default';
  };

  const currentVariant = getVariant();

  const styles: Record<BadgeVariant, string> = {
    critical: 'bg-red-500/10 border-red-500/30 text-red-400',
    high: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    medium: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    low: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    error: 'bg-red-500/10 border-red-500/30 text-red-400',
    default: 'bg-zinc-800/40 border-zinc-800 text-zinc-400',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs font-semibold font-mono tracking-tight uppercase leading-none ${styles[currentVariant]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          currentVariant === 'critical' || currentVariant === 'error'
            ? 'bg-red-500'
            : currentVariant === 'high'
            ? 'bg-orange-500'
            : currentVariant === 'medium' || currentVariant === 'warning'
            ? 'bg-amber-500'
            : currentVariant === 'low' || currentVariant === 'success'
            ? 'bg-emerald-500'
            : currentVariant === 'info'
            ? 'bg-blue-500'
            : 'bg-zinc-500'
        }`}
      />
      {value}
    </span>
  );
}
