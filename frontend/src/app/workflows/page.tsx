'use client';

import React, { useState } from 'react';
import { GitCommit, Plus, X } from 'lucide-react';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { WorkflowTable } from '../../components/workflows/WorkflowTable';
import { useWorkflows, useCreateWorkflow } from '../../hooks/useWorkflows';
import { useAuthStore } from '../../stores/auth';
import { useScopeStore } from '../../stores/scope';

function WorkflowsContent() {
  const { user } = useAuthStore();
  const { selectedScopeId } = useScopeStore();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [wfName, setWfName] = useState('');
  const [wfDefRaw, setWfDefRaw] = useState('{\n  "plugins": ["dnsx", "nmap", "nuclei"]\n}');
  const [formError, setFormError] = useState<string | null>(null);

  // Queries
  const { data: workflowsRes, isLoading, error } = useWorkflows();
  const createMutation = useCreateWorkflow();

  const isWriter = user?.role === 'admin' || user?.role === 'operator';
  const workflows = workflowsRes?.data || [];

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!wfName.trim()) {
      setFormError('Workflow name is required.');
      return;
    }

    try {
      const parsedDef = JSON.parse(wfDefRaw);
      createMutation.mutate(
        {
          name: wfName.trim(),
          definition: parsedDef,
        },
        {
          onSuccess: () => {
            setIsFormOpen(false);
            setWfName('');
            setWfDefRaw('{\n  "plugins": ["dnsx", "nmap", "nuclei"]\n}');
          },
        }
      );
    } catch (err: any) {
      setFormError(`Invalid JSON definition: ${err.message || 'JSON Syntax Error'}`);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Header Panel */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <GitCommit className="h-5 w-5 text-indigo-500" />
                <h1 className="text-2xl font-bold text-white tracking-tight">Scan Workflows</h1>
              </div>
              <p className="text-zinc-400 text-xs leading-normal max-w-xl">
                Create and manage vulnerability scanning orchestrators. Select a scope context in the header to launch executions.
              </p>
            </div>
            {isWriter && (
              <button
                onClick={() => setIsFormOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-lg shadow-indigo-900/20 cursor-pointer transition-colors"
              >
                <Plus className="h-4 w-4" />
                Define Playbook
              </button>
            )}
          </div>

          {/* Active Context Banner Warning */}
          {!selectedScopeId && (
            <div className="p-3 bg-amber-950/20 border border-amber-900/30 rounded-lg text-amber-400 text-xs font-mono text-center">
              Active context scope is not selected. You cannot launch scan workflow execution runs.
            </div>
          )}

          {/* Table Container */}
          {error ? (
            <div className="p-6 rounded-xl border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
              System request failed: {error.message || 'Could not fetch workflows'}
            </div>
          ) : (
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
              <WorkflowTable workflows={workflows} isLoading={isLoading} />
            </div>
          )}
        </main>
      </div>

      {/* Creation Modal */}
      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setIsFormOpen(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-zinc-900 bg-zinc-950 p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <button
              onClick={() => setIsFormOpen(false)}
              className="absolute top-4 right-4 p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-lg font-bold text-white tracking-tight mb-4">Define Scan Playbook</h3>
            {formError && (
              <div className="mb-4 p-3 rounded-lg border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
                {formError}
              </div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Workflow Name</label>
                <input
                  type="text"
                  value={wfName}
                  onChange={(e) => setWfName(e.target.value)}
                  placeholder="e.g. Discovery scan"
                  className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500 rounded-lg p-2.5 text-sm text-white placeholder-zinc-650 outline-none"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Playbook configuration (JSON)</label>
                <textarea
                  value={wfDefRaw}
                  onChange={(e) => setWfDefRaw(e.target.value)}
                  rows={5}
                  className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500 rounded-lg p-2.5 text-sm font-mono text-zinc-300 outline-none resize-none"
                  required
                />
              </div>
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-900">
                <button
                  type="button"
                  onClick={() => setIsFormOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white bg-transparent hover:bg-zinc-900/50 border border-zinc-800 rounded-lg transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {createMutation.isPending && (
                    <span className="h-3 w-3 animate-spin rounded-full border-t-white border-r-transparent border-b-white border-l-transparent border" />
                  )}
                  Create Playbook
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function WorkflowsPage() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <WorkflowsContent />
    </RouteGuard>
  );
}
