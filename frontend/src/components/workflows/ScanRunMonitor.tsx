import React from 'react';
import { Terminal, ShieldAlert, XCircle, RefreshCw } from 'lucide-react';
import { ScanRun, WorkflowEvent } from '../../types/workflow';
import { StatusBadge } from '../shared/StatusBadge';
import { useAuthStore } from '../../stores/auth';
import { useCancelScanRun } from '../../hooks/useWorkflows';

interface ScanRunMonitorProps {
  scanRun: ScanRun;
  events: WorkflowEvent[];
  isRefetching?: boolean;
}

export function ScanRunMonitor({ scanRun, events, isRefetching = false }: ScanRunMonitorProps) {
  const { user } = useAuthStore();
  const cancelMutation = useCancelScanRun();

  const isWriter = user?.role === 'admin' || user?.role === 'operator';
  const isTerminal = ['completed', 'failed', 'cancelled'].includes(scanRun.status);

  const handleCancel = () => {
    if (window.confirm('Are you sure you want to request cancellation for this Celery background process?')) {
      cancelMutation.mutate(scanRun.id);
    }
  };

  return (
    <div className="space-y-6">
      {/* Run Metadata Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Status */}
        <div className="bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col justify-between">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Run State</span>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge value={scanRun.status} />
            {isRefetching && !isTerminal && (
              <RefreshCw className="h-3.5 w-3.5 text-indigo-500 animate-spin" />
            )}
          </div>
        </div>

        {/* Start Time */}
        <div className="bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col justify-between">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Started At</span>
          <span className="mt-2 text-xs font-mono text-zinc-300">
            {scanRun.start_ts ? new Date(scanRun.start_ts).toLocaleString() : '-'}
          </span>
        </div>

        {/* End Time */}
        <div className="bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col justify-between">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Completed At</span>
          <span className="mt-2 text-xs font-mono text-zinc-300">
            {scanRun.end_ts ? new Date(scanRun.end_ts).toLocaleString() : 'In Progress...'}
          </span>
        </div>

        {/* Operations */}
        <div className="bg-zinc-950/40 p-4 rounded-xl border border-zinc-900 flex flex-col justify-between">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Controller</span>
          <div className="mt-2">
            {!isTerminal ? (
              <button
                onClick={handleCancel}
                disabled={!isWriter || cancelMutation.isPending}
                className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-950 bg-red-950/20 text-red-400 hover:bg-red-600 hover:text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer font-semibold text-xs w-full"
              >
                <XCircle className="h-3.5 w-3.5" />
                Cancel Run
              </button>
            ) : (
              <span className="text-xs text-zinc-600 font-mono italic">Task Terminated</span>
            )}
          </div>
        </div>
      </div>

      {/* Metrics Summary if exists */}
      {scanRun.metrics && Object.keys(scanRun.metrics).length > 0 && (
        <div className="bg-zinc-950/40 p-5 rounded-xl border border-zinc-900 space-y-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Scan Discoveries Metric Summary</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(scanRun.metrics).map(([key, val]) => (
              <div key={key} className="bg-zinc-900/40 p-3 rounded-lg border border-zinc-900 font-mono">
                <span className="text-[10px] text-zinc-500 uppercase block truncate">{key.replace('_', ' ')}</span>
                <span className="text-base font-bold text-white mt-1 block">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Console log Event Feed */}
      <div className="bg-zinc-950 border border-zinc-900 rounded-xl overflow-hidden shadow-2xl flex flex-col h-96">
        {/* Terminal Header */}
        <div className="bg-zinc-900/60 px-4 py-3 border-b border-zinc-900 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <Terminal className="h-4 w-4 text-indigo-400" />
            Execution Lifecycle Event Console Logs
          </div>
          <span className="text-[10px] text-zinc-600 font-mono">Real-time Stream</span>
        </div>

        {/* Terminal logs list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs text-zinc-400 bg-zinc-950 select-text">
          {events.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 italic">
              <ShieldAlert className="h-8 w-8 text-zinc-800 mb-2" />
              Initializing runner thread. Listening for Celery payload events...
            </div>
          ) : (
            events.map((evt) => (
              <div
                key={evt.id}
                className="flex flex-col md:flex-row md:items-start gap-2 md:gap-4 py-1 border-b border-zinc-900/30 last:border-0 hover:bg-zinc-900/10 transition-colors"
              >
                {/* Time */}
                <span className="text-zinc-600 shrink-0 select-none">
                  [{new Date(evt.timestamp).toLocaleTimeString()}]
                </span>
                {/* Type Badge */}
                <span className={`shrink-0 uppercase text-[10px] px-1.5 py-0.5 rounded font-semibold border ${
                  evt.event_type.includes('fail') || evt.event_type.includes('error')
                    ? 'bg-red-500/10 border-red-500/20 text-red-400'
                    : evt.event_type.includes('start') || evt.event_type.includes('run')
                    ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400'
                    : 'bg-zinc-800 border-zinc-700/50 text-zinc-400'
                }`}>
                  {evt.event_type}
                </span>
                {/* Payload details */}
                <div className="flex-1 text-zinc-300">
                  {evt.payload?.message || evt.payload?.error || JSON.stringify(evt.payload)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
