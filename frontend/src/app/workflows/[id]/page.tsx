'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, GitCommit } from 'lucide-react';
import { Sidebar } from '../../../components/navigation/Sidebar';
import { Topbar } from '../../../components/navigation/Topbar';
import { RouteGuard } from '../../../components/auth/RouteGuard';
import { ScanRunMonitor } from '../../../components/workflows/ScanRunMonitor';
import { LoadingState } from '../../../components/shared/LoadingState';
import { ErrorState } from '../../../components/shared/ErrorState';
import { useScanRunDetails, useWorkflowEvents } from '../../../hooks/useWorkflows';

interface PageProps {
  params: Promise<{ id: string }>;
}

function ScanRunTrackingContent({ params }: PageProps) {
  const { id: runId } = React.use(params);

  // Query ScanRun details (polls every 5s unless in terminal state)
  const { data: runRes, isLoading: loadingRun, error: runErr, isRefetching } = useScanRunDetails(runId);

  const scanRun = runRes?.data;
  const workflowId = scanRun?.workflow_id || '';

  // Query lifecycle events for this workflow
  const { data: eventsRes, isLoading: loadingEvents } = useWorkflowEvents(workflowId, {
    page_size: 100, // retrieve latest 100 events
  });

  const events = eventsRes?.data || [];

  if (loadingRun) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 flex items-center justify-center">
            <LoadingState message="Connecting to execution process channel..." />
          </div>
        </div>
      </div>
    );
  }

  if (runErr || !scanRun) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 p-6">
            <ErrorState message={runErr?.message || 'Could not locate scan run execution records.'} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Back Navigation */}
          <div className="flex items-center gap-2">
            <Link
              href="/workflows"
              className="flex items-center gap-1 text-xs font-semibold text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to Playbooks
            </Link>
          </div>

          {/* Header Panel */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <GitCommit className="h-5 w-5 text-indigo-500" />
                <h1 className="text-xl font-bold text-white tracking-tight">Run Execution Tracker</h1>
              </div>
              <p className="text-zinc-400 text-xs font-mono">
                Scan Run UUID: {scanRun.id} • Workflow Playbook ID: {scanRun.workflow_id}
              </p>
            </div>
          </div>

          {/* Monitor Dashboard */}
          <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
            <ScanRunMonitor
              scanRun={scanRun}
              events={events}
              isRefetching={isRefetching}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ScanRunDetailPage({ params }: PageProps) {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <ScanRunTrackingContent params={params} />
    </RouteGuard>
  );
}
