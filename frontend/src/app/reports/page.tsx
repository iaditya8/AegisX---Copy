'use client';

import React from 'react';
import { FileText } from 'lucide-react';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { ReportDashboard } from '../../components/reports/ReportDashboard';
import { LoadingState } from '../../components/shared/LoadingState';
import { ErrorState } from '../../components/shared/ErrorState';
import { useDashboardSummary, useDashboardTrends, useExposureReport } from '../../hooks/useReports';

function ReportsContent() {
  const { data: summaryRes, isLoading: loadingSummary, error: summaryErr } = useDashboardSummary();
  const { data: trendsRes, isLoading: loadingTrends } = useDashboardTrends(30);
  const { data: exposureRes, isLoading: loadingExposure } = useExposureReport();

  const summary = summaryRes?.data;
  const trends = trendsRes?.data || null;
  const exposure = exposureRes?.data || null;

  const isLoading = loadingSummary || loadingTrends || loadingExposure;

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
                <FileText className="h-5 w-5 text-indigo-500" />
                <h1 className="text-2xl font-bold text-white tracking-tight">Reports & Exports</h1>
              </div>
              <p className="text-zinc-400 text-xs leading-normal max-w-xl">
                Review security posture summaries, severity statistics, and download executive analytical data.
              </p>
            </div>
          </div>

          {/* Main Content */}
          {isLoading ? (
            <div className="h-[50vh] flex items-center justify-center">
              <LoadingState message="Consolidating dashboard posture telemetry..." />
            </div>
          ) : summaryErr || !summary ? (
            <ErrorState message={summaryErr?.message || 'Could not fetch dashboard summary statistics.'} />
          ) : (
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
              <ReportDashboard summary={summary} trends={trends} exposure={exposure} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <ReportsContent />
    </RouteGuard>
  );
}
