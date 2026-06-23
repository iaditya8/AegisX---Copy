'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, ShieldAlert, CheckCircle, EyeOff, FileText, Database } from 'lucide-react';
import { Sidebar } from '../../../components/navigation/Sidebar';
import { Topbar } from '../../../components/navigation/Topbar';
import { RouteGuard } from '../../../components/auth/RouteGuard';
import { StatusBadge } from '../../../components/shared/StatusBadge';
import { LoadingState } from '../../../components/shared/LoadingState';
import { ErrorState } from '../../../components/shared/ErrorState';
import { EmptyState } from '../../../components/shared/EmptyState';
import { useAuthStore } from '../../../stores/auth';
import {
  useFindingDetails,
  useFindingEvidence,
  useAcknowledgeFinding,
  useResolveFinding,
  useSuppressFinding,
} from '../../../hooks/useFindings';

interface PageProps {
  params: Promise<{ id: string }>;
}

function FindingDetailContent({ params }: PageProps) {
  const { id } = React.use(params);
  const { user } = useAuthStore();

  // Queries
  const { data: detailsRes, isLoading: loadingDetails, error: detailsErr } = useFindingDetails(id);
  const { data: evidenceRes, isLoading: loadingEvidence } = useFindingEvidence(id);

  // Mutations
  const ackMutation = useAcknowledgeFinding();
  const resolveMutation = useResolveFinding();
  const suppressMutation = useSuppressFinding();

  const finding = detailsRes?.data;
  const evidences = evidenceRes?.data || [];

  const isWriter = user?.role === 'admin' || user?.role === 'operator';
  const isPending = ackMutation.isPending || resolveMutation.isPending || suppressMutation.isPending;

  if (loadingDetails || loadingEvidence) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 flex items-center justify-center">
            <LoadingState message="Decoding vulnerability forensics..." />
          </div>
        </div>
      </div>
    );
  }

  if (detailsErr || !finding) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 p-6">
            <ErrorState message={detailsErr?.message || 'Specified vulnerability finding records not found.'} />
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
              href="/findings"
              className="flex items-center gap-1 text-xs font-semibold text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to findings Log
            </Link>
          </div>

          {/* Finding Header Panel */}
          <div className="p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-3 max-w-2xl text-left">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge value={finding.severity} />
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-semibold ${
                  finding.status === 'open'
                    ? 'bg-red-500/10 border-red-500/20 text-red-400'
                    : finding.status === 'acknowledged'
                    ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                    : finding.status === 'resolved'
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-zinc-800 border-zinc-800 text-zinc-400'
                }`}>
                  {finding.status}
                </span>
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight leading-tight">{finding.title}</h1>
              <p className="text-xs text-zinc-400 font-mono">
                Asset Target ID: {finding.asset_id} • Scanner: {finding.source_plugin || 'system'}
              </p>
            </div>

            {/* Triage Actions Panel (RBAC protected) */}
            <div className="flex flex-col gap-2 min-w-[200px]">
              <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider font-mono text-left md:text-right">
                Triage Decisions
              </span>
              <div className="flex flex-wrap md:flex-col gap-2 mt-1">
                {/* Acknowledge */}
                <button
                  onClick={() => ackMutation.mutate(finding.id)}
                  disabled={!isWriter || isPending || finding.status === 'acknowledged'}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
                  Acknowledge
                </button>
                {/* Resolve */}
                <button
                  onClick={() => resolveMutation.mutate(finding.id)}
                  disabled={!isWriter || isPending || finding.status === 'resolved'}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  Resolve Fix
                </button>
                {/* Suppress */}
                <button
                  onClick={() => suppressMutation.mutate(finding.id)}
                  disabled={!isWriter || isPending || finding.status === 'suppressed'}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <EyeOff className="h-3.5 w-3.5 text-zinc-500" />
                  Suppress
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Description & Details */}
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl md:col-span-2 space-y-4 text-left">
              <div>
                <h3 className="text-sm font-semibold text-white tracking-tight">Vulnerability Description</h3>
                <p className="text-xs text-zinc-400 leading-relaxed mt-2 whitespace-pre-wrap">
                  {finding.description || 'No description provided for this vulnerability occurrence.'}
                </p>
              </div>

              {finding.metadata_json && Object.keys(finding.metadata_json).length > 0 && (
                <div className="pt-4 border-t border-zinc-900">
                  <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Metadata payload</h4>
                  <pre className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-lg text-xs font-mono text-indigo-300 overflow-x-auto select-all">
                    {JSON.stringify(finding.metadata_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Template Information Card */}
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl flex flex-col justify-between space-y-4 text-left">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-white font-semibold text-xs uppercase tracking-wider">
                  <FileText className="h-4 w-4 text-indigo-400" />
                  Rule template
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase block font-mono">Template Name</span>
                  <span className="text-xs font-bold text-zinc-300">{finding.template_name}</span>
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase block font-mono">Template ID</span>
                  <span className="text-xs text-zinc-400 font-mono break-all">{finding.template_id}</span>
                </div>
              </div>
              <div className="pt-4 border-t border-zinc-900 text-xs font-mono text-zinc-500 space-y-1">
                <div>First seen: {new Date(finding.first_seen).toLocaleString()}</div>
                <div>Last seen: {new Date(finding.last_seen).toLocaleString()}</div>
              </div>
            </div>
          </div>

          {/* Forensics Evidence Tab */}
          <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl space-y-4 text-left">
            <div className="flex items-center gap-2 text-white font-semibold text-sm">
              <Database className="h-4 w-4 text-indigo-400" />
              Forensics evidence Data
            </div>

            {evidences.length === 0 ? (
              <EmptyState
                title="No Forensics Evidence"
                description="No matching raw HTTP or console payload signatures were captured as evidence."
              />
            ) : (
              <div className="space-y-6">
                {evidences.map((ev, idx) => (
                  <div key={ev.id || idx} className="space-y-3 border-b border-zinc-900 pb-6 last:border-0 last:pb-0">
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50 uppercase font-semibold">
                        Type: {ev.evidence_type}
                      </span>
                      <span className="text-zinc-500">Matcher: {ev.matcher_name || 'N/A'}</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Raw request */}
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase font-mono block mb-1">Raw request</span>
                        <pre className="bg-zinc-950 border border-zinc-900 p-4 rounded-lg text-xs font-mono text-zinc-400 overflow-x-auto max-h-60 select-all">
                          {ev.raw_request || 'No raw request captured.'}
                        </pre>
                      </div>
                      {/* Raw response */}
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase font-mono block mb-1">Raw response</span>
                        <pre className="bg-zinc-950 border border-zinc-900 p-4 rounded-lg text-xs font-mono text-zinc-400 overflow-x-auto max-h-60 select-all">
                          {ev.raw_response || 'No raw response captured.'}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function FindingDetailPage({ params }: PageProps) {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <FindingDetailContent params={params} />
    </RouteGuard>
  );
}
