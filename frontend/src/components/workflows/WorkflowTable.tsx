import React, { useState } from 'react';
import { Play, ArrowRight, Eye } from 'lucide-react';
import Link from 'next/link';
import { Workflow } from '../../types/workflow';
import { useAuthStore } from '../../stores/auth';
import { useScopeStore } from '../../stores/scope';
import { DataTable, Column } from '../shared/DataTable';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { useStartWorkflow } from '../../hooks/useWorkflows';

interface WorkflowTableProps {
  workflows: Workflow[];
  isLoading: boolean;
}

export function WorkflowTable({ workflows, isLoading }: WorkflowTableProps) {
  const { user } = useAuthStore();
  const { selectedScopeId } = useScopeStore();
  const [triggerId, setTriggerId] = useState<string | null>(null);

  const startMutation = useStartWorkflow();
  const isWriter = user?.role === 'admin' || user?.role === 'operator';

  const handleTriggerConfirm = () => {
    if (triggerId && selectedScopeId) {
      startMutation.mutate(
        {
          id: triggerId,
          data: {
            scope_id: selectedScopeId,
          },
        },
        {
          onSuccess: (res) => {
            setTriggerId(null);
            // Redirect to scan run execution tracking details
            const runId = res.data?.run_id;
            if (runId && typeof window !== 'undefined') {
              window.location.href = `/workflows/${runId}`;
            }
          },
        }
      );
    }
  };

  const columns: Column<Workflow>[] = [
    {
      key: 'name',
      label: 'Workflow Name',
      sortable: true,
      render: (wf) => <span className="font-semibold text-white">{wf.name}</span>,
    },
    {
      key: 'state',
      label: 'State',
      sortable: true,
      render: (wf) => (
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-semibold ${
          wf.state === 'active'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            : wf.state === 'draft'
            ? 'bg-zinc-800 border-zinc-800 text-zinc-500'
            : 'bg-red-500/10 border-red-500/20 text-red-400'
        }`}>
          {wf.state}
        </span>
      ),
    },
    {
      key: 'definition',
      label: 'Definition Summary',
      render: (wf) => {
        const plugins = wf.definition?.plugins || [];
        return (
          <span className="text-xs text-zinc-400 font-mono">
            {plugins.length} scanner modules configured
          </span>
        );
      },
    },
    {
      key: 'updated_at',
      label: 'Last Modified',
      sortable: true,
      render: (wf) => (
        <span className="text-xs text-zinc-500 font-mono">
          {wf.updated_at ? new Date(wf.updated_at).toLocaleString() : '-'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (wf) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTriggerId(wf.id)}
            disabled={!isWriter || !selectedScopeId || startMutation.isPending}
            title={
              !isWriter
                ? 'Unauthorized to launch scans'
                : !selectedScopeId
                ? 'Select an active scope context first'
                : 'Execute Scan Workflow'
            }
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-950 bg-indigo-950/20 text-indigo-400 hover:bg-indigo-600 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer font-semibold text-xs"
          >
            <Play className="h-3 w-3 fill-current" />
            Launch Run
          </button>
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={workflows}
        isLoading={isLoading}
        emptyMessage="No workflows configured. Define a scan playbook first."
      />

      <ConfirmDialog
        isOpen={!!triggerId}
        title="Trigger scan Execution"
        description="Verify scope targets and scan configuration before executing this Celery workflow background execution run."
        confirmLabel="Execute Run"
        isLoading={startMutation.isPending}
        onConfirm={handleTriggerConfirm}
        onClose={() => setTriggerId(null)}
      />
    </>
  );
}
